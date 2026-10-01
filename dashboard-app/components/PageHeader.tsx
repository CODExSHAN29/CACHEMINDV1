import { ReactNode } from "react";
export default function PageHeader({ index, title, description, action }: { index: string; title: string; description?: string; action?: ReactNode }) {
  return <header className="page-heading"><div><div className="section-index">{index}</div><h1>{title}</h1>{description && <p>{description}</p>}</div>{action}</header>;
}
