export default function Panel({
  title,
  action,
  children,
  bodyClass = "panel-body",
  className = "",
}: {
  title?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
  bodyClass?: string;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      {title && (
        <header className="panel-head">
          <h3 className="panel-title">{title}</h3>
          {action}
        </header>
      )}
      <div className={bodyClass}>{children}</div>
    </section>
  );
}
