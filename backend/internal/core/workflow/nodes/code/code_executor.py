"""Code 节点的沙箱执行器。

朴素实现常是「顶层 AST 检查 + 裸 exec」，可执行任意 Python，公网部署不可接受。
本实现三层硬化（仍非真隔离，防护层级：AST 静态拒绝 → 受限 builtins → 子进程资源域）：
1. AST 全树扫描：只允许单个 ``def main(params)``；拒绝 import、global/nonlocal、
   一切双下划线名字/属性（封 ``__class__``/``__subclasses__`` 逃逸链）与危险内置名。
2. ``exec`` 时替换 ``__builtins__`` 为白名单字典，main 函数的全局查找被限制在白名单内。
3. 在 spawn 子进程中执行：硬超时（terminate 可杀死死循环，线程做不到）、
   RLIMIT_AS 内存上限、结果只经 JSON 字节回传（绝不 unpickle 子进程数据——
   沙箱代码若能构造恶意 pickle 即可在父进程 RCE）。

本模块被 spawn 子进程重新 import，必须保持轻量：只依赖标准库，严禁引 Flask/项目模块。
"""
import ast
import json
import multiprocessing
from typing import Any

# 受限 builtins 白名单（main 函数内可用的全部内置能力）
_SAFE_BUILTIN_NAMES = (
    "abs", "all", "any", "bin", "bool", "chr", "dict", "divmod", "enumerate",
    "filter", "float", "format", "frozenset", "hash", "hex", "int", "isinstance",
    "issubclass", "iter", "len", "list", "map", "max", "min", "next", "oct",
    "ord", "pow", "print", "range", "repr", "reversed", "round", "set", "slice",
    "sorted", "str", "sum", "tuple", "zip",
    # 常用异常类（业务代码 raise/except 用）
    "Exception", "ValueError", "TypeError", "KeyError", "IndexError",
    "AttributeError", "RuntimeError", "ZeroDivisionError", "ArithmeticError",
    "StopIteration",
)

# AST 中直接拒绝的名字（无论作为 Name 还是 Attribute）
_BLOCKED_NAMES = frozenset({
    "eval", "exec", "compile", "open", "input", "breakpoint", "memoryview",
    "globals", "locals", "vars", "dir", "getattr", "setattr", "delattr",
    "type", "super", "object", "classmethod", "staticmethod", "property",
    "exit", "quit", "help", "copyright", "credits", "license",
})


def validate_code(code: str) -> None:
    """AST 全树校验；不通过抛 ValueError（调用方转业务异常）。"""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise ValueError(f"代码语法错误：{e}")

    # 1.顶层只允许一个 def main(params)
    main_func = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            if node.name != "main":
                raise ValueError("代码中不能包含其他函数，只能有main函数")
            if main_func is not None:
                raise ValueError("代码中只能有一个main函数")
            if (
                len(node.args.args) != 1
                or node.args.args[0].arg != "params"
                or node.args.vararg is not None
                or node.args.kwarg is not None
                or node.args.kwonlyargs
                or node.args.posonlyargs
            ):
                raise ValueError("main函数必须只有一个参数，且参数为params")
            if node.decorator_list:
                raise ValueError("main函数不允许使用装饰器")
            main_func = node
        else:
            raise ValueError("代码中只能包含函数定义，不允许其他语句存在")

    if main_func is None:
        raise ValueError("代码中必须包含名为main的函数")

    # 2.全树扫描拒绝危险结构（只查顶层逃逸面太大）
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise ValueError("代码中不允许使用import语句")
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            raise ValueError("代码中不允许使用global/nonlocal语句")
        if isinstance(node, (ast.AsyncFunctionDef, ast.Await, ast.AsyncFor, ast.AsyncWith)):
            raise ValueError("代码中不允许使用async语法")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ValueError(f"代码中不允许访问双下划线属性：{node.attr}")
        if isinstance(node, ast.Name):
            if node.id.startswith("__"):
                raise ValueError(f"代码中不允许使用双下划线名字：{node.id}")
            if node.id in _BLOCKED_NAMES:
                raise ValueError(f"代码中不允许使用：{node.id}")


def _build_safe_builtins() -> dict[str, Any]:
    import builtins

    return {name: getattr(builtins, name) for name in _SAFE_BUILTIN_NAMES if hasattr(builtins, name)}


def _child_worker(code: str, params: dict, max_output_bytes: int, memory_limit_bytes: int, conn) -> None:
    """spawn 子进程入口：设资源上限 → 受限 exec → 结果 JSON 字节回传。"""

    def reply(payload: dict) -> None:
        try:
            conn.send_bytes(json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8"))
        except Exception:
            pass

    # 1.内存上限（best-effort，部分平台不支持 RLIMIT_AS）
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (memory_limit_bytes, memory_limit_bytes))
    except Exception:
        pass

    # 2.受限执行
    try:
        local_vars: dict[str, Any] = {}
        exec(code, {"__builtins__": _build_safe_builtins()}, local_vars)

        main = local_vars.get("main")
        if not callable(main):
            reply({"ok": False, "error": "main函数必须是一个可调用的函数"})
            return

        result = main(params)
        if not isinstance(result, dict):
            reply({"ok": False, "error": "main函数的返回值必须是一个字典"})
            return

        # 3.JSON 规整（剥掉沙箱代码可能返回的奇怪对象）+ 输出大小上限
        body = json.dumps(result, ensure_ascii=False, default=str)
        if len(body.encode("utf-8")) > max_output_bytes:
            reply({"ok": False, "error": f"代码输出超过大小上限（{max_output_bytes} 字节）"})
            return

        reply({"ok": True, "result": json.loads(body)})
    except Exception as e:
        reply({"ok": False, "error": f"{type(e).__name__}: {str(e)[:500]}"})


def execute_code(
    code: str,
    params: dict,
    *,
    timeout_seconds: int = 5,
    max_output_bytes: int = 65536,
    memory_limit_bytes: int = 256 * 1024 * 1024,
) -> dict:
    """校验并在沙箱子进程中执行代码，返回 main 的 dict 结果；失败抛 ValueError。"""
    validate_code(code)

    ctx = multiprocessing.get_context("spawn")
    reader, writer = ctx.Pipe(duplex=False)
    process = ctx.Process(
        target=_child_worker,
        args=(code, params, max_output_bytes, memory_limit_bytes, writer),
        daemon=True,
    )
    process.start()
    writer.close()

    try:
        # spawn 启动有 ~百毫秒级开销，额外给 3 秒宽限，避免把启动时间算进用户代码超时
        if not reader.poll(timeout_seconds + 3):
            raise ValueError(f"代码执行超时（{timeout_seconds} 秒）")
        try:
            raw = reader.recv_bytes(max_output_bytes + 4096)
        except EOFError:
            raise ValueError("代码执行进程异常退出（可能触发内存上限）")
        except OSError:
            raise ValueError(f"代码输出超过大小上限（{max_output_bytes} 字节）")
    finally:
        reader.close()
        if process.is_alive():
            process.terminate()
            process.join(1)
            if process.is_alive():
                process.kill()
        process.join(1)

    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        raise ValueError("代码执行结果解析失败")

    if not payload.get("ok"):
        raise ValueError(payload.get("error") or "Python代码执行出错")
    result = payload.get("result")
    if not isinstance(result, dict):
        raise ValueError("main函数的返回值必须是一个字典")
    return result
