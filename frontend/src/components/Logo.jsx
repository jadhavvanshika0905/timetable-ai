/** Small timetable-grid mark + wordmark. `light` = for dark backgrounds. */
export default function Logo({ light = false, size = 30, text = true }) {
  return (
    <span className="inline-flex items-center gap-2.5">
      <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
        <rect x="2" y="2" width="12" height="12" rx="3.5" fill={light ? "#ffffff" : "#0e5d63"} />
        <rect x="18" y="2" width="12" height="12" rx="3.5" fill="#f2a33a" />
        <rect x="2" y="18" width="12" height="12" rx="3.5" fill="#7c6cf0" />
        <rect x="18" y="18" width="12" height="12" rx="3.5" fill="none" stroke={light ? "#ffffff" : "#0e5d63"} strokeWidth="2.5" />
      </svg>
      {text && (
        <span className={`font-display text-xl font-bold tracking-tight ${light ? "text-white" : "text-brand"}`}>
          Timetable
        </span>
      )}
    </span>
  );
}