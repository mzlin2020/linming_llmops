/** 占位页:模块尚未在当前子阶段实现时的中性提示。 */
export function Placeholder({ title, note }: { title: string; note?: string }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
      <h2 className="text-lg font-semibold">{title}</h2>
      {note && <p className="text-sm text-muted-foreground">{note}</p>}
    </div>
  );
}
