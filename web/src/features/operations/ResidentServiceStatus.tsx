import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useAuthToken } from "../../shared/api/auth-context";
import { fetchManagementReadiness } from "../../shared/api/configuration-api";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { RefreshControl } from "../../shared/ui/RefreshControl";

const SERVICES = ["api", "worker", "scheduler", "notification-worker"] as const;
const REASONS: Record<string, string> = {
  unconfigured: "等待业务配置：前往系统设置检查 Active，再配置所需业务能力。",
  configuration_unavailable:
    "Active 配置不可用：前往系统设置检查并恢复已发布配置。",
  secret_unavailable: "所需密钥不可用：请管理员修复部署密钥配置。",
  database_unavailable:
    "数据库不可用：请管理员恢复数据库访问，服务将安全重试。",
  schema_unsupported: "数据库或配置版本不兼容：请管理员按升级与恢复流程处理。",
};

function record(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

export function ResidentServiceStatus() {
  const token = useAuthToken();
  const query = useQuery({
    queryKey: ["management.resident-readiness"],
    queryFn: () => fetchManagementReadiness(token),
    enabled: token !== null,
    retry: false,
    refetchInterval: 15_000,
  });
  return (
    <section className="mf-count-section" aria-label="常驻服务状态">
      <h3>常驻服务状态</h3>
      <AuthorizedReadBoundary query={query} unavailableTitle="服务状态暂不可用">
        {({ data, refresh, isFetching }) => {
          const infrastructure = record(data?.infrastructure);
          const services = record(infrastructure.services);
          return (
            <>
              <RefreshControl onRefresh={refresh} refreshing={isFetching} />
              <p>
                基础设施健康与业务可用性分别报告；等待配置不会授予执行权限。
              </p>
              {!data ? <p>正在读取服务状态。</p> : null}
              {data && !infrastructure.services ? (
                <p>
                  无法读取服务注册状态。请管理员检查数据库与服务部署，然后刷新。
                </p>
              ) : null}
              {data && infrastructure.services ? (
                <ul>
                  {SERVICES.map((name) => {
                    const state = record(services[name]);
                    const reason =
                      typeof state.waitingReason === "string"
                        ? state.waitingReason
                        : "";
                    return (
                      <li key={name}>
                        <strong>{name}</strong> —{" "}
                        {state.ready === true
                          ? "基础设施就绪"
                          : "基础设施未就绪"}
                        。
                        {state.ready !== true
                          ? state.condition === "schema_mismatch"
                            ? "请管理员按升级与恢复流程处理版本不兼容。"
                            : "请管理员检查服务进程及数据库连接，再刷新状态。"
                          : state.waiting === true
                            ? (REASONS[reason] ??
                              "业务等待中，请检查配置及持久任务状态。")
                            : "服务未报告等待；具体操作仍需通过业务就绪与权限检查。"}
                      </li>
                    );
                  })}
                </ul>
              ) : null}
              <Link to="/configuration">前往系统设置</Link>
            </>
          );
        }}
      </AuthorizedReadBoundary>
    </section>
  );
}
