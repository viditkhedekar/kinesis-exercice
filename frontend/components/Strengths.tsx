export default function Strengths({ items }: { items: string[] }) {
  return (
    <div className="card p-5">
      <h3 className="font-semibold mb-3">Strengths</h3>
      {items.length === 0 ? (
        <p className="text-muted text-sm">Keep working — strengths will appear as your technique improves.</p>
      ) : (
        <ul className="space-y-2">
          {items.map((s) => (
            <li key={s} className="flex items-center gap-2 text-sm text-fg">
              <span className="text-good">✓</span>
              {s}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
