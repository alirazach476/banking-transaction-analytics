import React, { useId } from "react";

// NovaBank mark: a squircle with a blue-violet-teal gradient, an "N" whose diagonal is a rising chart line, a glowing node at the peak, and a faint orbit ring.
export function LogoMark({ size = 36, className = "" }) {
  const id = useId().replace(/:/g, "");
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 48 48" role="img" aria-label="NovaBank logo" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id={id + "g"} x1="4" y1="2" x2="44" y2="46" gradientUnits="userSpaceOnUse"><stop offset="0" stopColor="#4f8cff" /><stop offset=".55" stopColor="#7c5cf0" /><stop offset="1" stopColor="#14c8b4" /></linearGradient>
        <linearGradient id={id + "s"} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#fff" stopOpacity=".35" /><stop offset="1" stopColor="#fff" stopOpacity="0" /></linearGradient>
        <radialGradient id={id + "n"}><stop offset="0" stopColor="#fff" /><stop offset="1" stopColor="#fff" stopOpacity="0" /></radialGradient>
      </defs>
      <rect x="1" y="1" width="46" height="46" rx="14" fill={`url(#${id}g)`} />
      <rect x="1" y="1" width="46" height="23" rx="14" fill={`url(#${id}s)`} />
      <ellipse cx="24" cy="24" rx="19" ry="7.5" transform="rotate(-32 24 24)" fill="none" stroke="#fff" strokeOpacity=".28" strokeWidth="1.4" />
      <path d="M14.5 34V14.5L33.5 33.5V13" fill="none" stroke="#fff" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="33.5" cy="13" r="7" fill={`url(#${id}n)`} opacity=".55" />
      <circle cx="33.5" cy="13" r="3" fill="#fff" />
    </svg>
  );
}

export default function Logo({ size = 36, tagline = true }) {
  return (
    <span className="logo-lockup">
      <LogoMark size={size} />
      <span className="wm"><b>Nova<i>Bank</i></b>{tagline && <small>Analytics Intelligence</small>}</span>
    </span>
  );
}
