const P = {
  shield: ["M12 3l8 3v6c0 4.5-3.2 8-8 9-4.8-1-8-4.5-8-9V6l8-3z", "M9 12l2 2 4-4"],
  chart: ["M4 19V5", "M4 19h16", "M8 15v-4", "M12 15V8", "M16 15v-6"],
  scale: ["M12 3v18", "M5 7h14", "M5 7l-3 7a3 3 0 006 0L5 7z", "M19 7l-3 7a3 3 0 006 0l-3-7z"],
  flask: ["M9 3h6", "M10 3v6L5 19a1.5 1.5 0 001.3 2h11.4A1.5 1.5 0 0019 19l-5-10V3"],
  clock: ["M12 21a9 9 0 100-18 9 9 0 000 18z", "M12 7v5l3 2"],
  eye: ["M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z", "M12 15a3 3 0 100-6 3 3 0 000 6z"],
  eyeOff: ["M3 3l18 18", "M10.6 6.1A10 10 0 0112 6c6.5 0 10 6 10 6a17 17 0 01-3.2 3.9M6.5 7.6A17 17 0 002 12s3.5 6 10 6a9.5 9.5 0 004-.9", "M9.9 9.9a3 3 0 004.2 4.2"],
  grid: ["M4 4h7v7H4z", "M13 4h7v7h-7z", "M4 13h7v7H4z", "M13 13h7v7h-7z"],
  teach: ["M3 4h18v12H3z", "M12 16v4", "M8 20h8"],
  book: ["M4 5a2 2 0 012-2h13v15H6a2 2 0 00-2 2V5z", "M4 20a2 2 0 002 2h13"],
  arrow: ["M5 12h14", "M13 6l6 6-6 6"],
  menu: ["M4 7h16", "M4 12h16", "M4 17h16"],
  close: ["M6 6l12 12", "M18 6L6 18"],
  check: ["M5 13l4 4L19 7"],
  user: ["M12 12a4 4 0 100-8 4 4 0 000 8z", "M4 21a8 8 0 0116 0"],
  lock: ["M6 11h12v10H6z", "M8 11V8a4 4 0 018 0v3"],
  spark: ["M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3z"],
  home: ["M3 11l9-8 9 8", "M5 10v10h14V10"],
};

export default function Icon({ name, size = 20, stroke = 1.8, className = "" }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      {(P[name] || []).map((d, i) => <path key={i} d={d} />)}
    </svg>
  );
}