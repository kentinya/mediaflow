import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useAuthToken } from "../../shared/api/auth-context";
import { AuthorizedReadBoundary } from "../../shared/auth/AuthorizedReadBoundary";
import { workerReadinessQueryOptions } from "./worker-query";

/** Old links never recover their former scope or submit work. */
export function ScanRetiredPage() {
  const token = useAuthToken();
  const query = useQuery(workerReadinessQueryOptions(token));
  return (
    <AuthorizedReadBoundary query={query}>
      {() => (
        <section className="mf-page">
          <h1>独立扫描已退役</h1>
          <p>
            未创建工作，也未执行发现。整理会在原工作流中完成发现和必要的稳定性观察。
          </p>
          <nav className="mf-actions" aria-label="扫描退役后的操作">
            <Link className="mf-button" to="/operations/organize/new">
              新建整理
            </Link>
            <Link to="/operations">返回任务中心</Link>
          </nav>
        </section>
      )}
    </AuthorizedReadBoundary>
  );
}
