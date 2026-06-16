import { useQuery } from "@tanstack/react-query";
import { Link, Outlet, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";

import { getDataset } from "@/api/datasets";
import { ModuleLayout } from "@/app-shell/ModuleLayout";
import { SidebarNav, type SidebarItem } from "@/components/shared/SidebarNav";

/** 知识库详情外壳：库名页头 + 子导航(文档/命中测试/设置) + Outlet。 */
export function DatasetDetailLayout() {
  const { id } = useParams();
  const datasetId = Number(id);

  const query = useQuery({
    queryKey: ["dataset", datasetId],
    queryFn: () => getDataset(datasetId),
    enabled: Number.isFinite(datasetId),
  });

  const nav: SidebarItem[] = [
    { to: `/datasets/${datasetId}/documents`, label: "文档" },
    { to: `/datasets/${datasetId}/hit-testing`, label: "命中测试" },
    { to: `/datasets/${datasetId}/settings`, label: "设置" },
  ];

  return (
    <ModuleLayout
      sidebar={
        <div className="space-y-3">
          <Link
            to="/datasets"
            className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" /> 知识库
          </Link>
          <p className="truncate px-1 font-semibold" title={query.data?.name}>
            {query.data?.name ?? "…"}
          </p>
          <SidebarNav items={nav} />
        </div>
      }
    >
      <Outlet />
    </ModuleLayout>
  );
}
