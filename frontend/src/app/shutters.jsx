import React, { useId, useState } from "react";
import step from "../assets/hero-step.webp";
import reel from "../assets/hero-reel.webp";
import "../styles/shutters.css";

const scenes = [
  { image: step, name: "Footsteps", caption: "A moment of contact.", position: "xMidYMid", y: -640, height: 1750 },
  { image: reel, name: "Recording", caption: "A performance captured.", position: "xMidYMid" },
];

export function Shutters() {
  const mask = useId();
  const [selected, setSelected] = useState(0);
  const [open, setOpen] = useState(false);
  return (
    <section className="shutters" data-open={open} aria-label="Photographic title" onKeyDown={(event) => {
      if (event.key === "Escape") setOpen(false);
    }}>
      <h1 className="shutters-heading">ORPHEUS</h1>
      <svg className="shutters-stage" viewBox="0 0 1400 600" aria-hidden="true">
        <defs>
          <mask id={mask} maskUnits="userSpaceOnUse" x="0" y="0" width="1400" height="600">
            <rect width="1400" height="600" fill="black" />
            <text x="50" y="465" textLength="1300" lengthAdjust="spacingAndGlyphs" className="shutters-letters" fill="white">ORPHEUS</text>
            {Array.from({ length: 7 }, (_, index) => (
              <rect key={index} x={index * 200} width="201" height="600" fill="white" className="shutter-blade" style={{ "--blade": index }} />
            ))}
          </mask>
        </defs>
        <g mask={`url(#${mask})`}>
          {scenes.map((scene, index) => (
            <image key={scene.name} href={scene.image} y={scene.y ?? 0} width="1400" height={scene.height ?? 600} preserveAspectRatio={`${scene.position} slice`} className="shutter-image" opacity={selected === index ? 1 : 0} />
          ))}
        </g>
      </svg>
      <div className="shutters-controls">
        <div className="shutters-scenes" aria-label="Choose photograph">
          {scenes.map((scene, index) => (
            <button key={scene.name} aria-pressed={selected === index} onClick={() => { setSelected(index); setOpen(true); }}>
              <img src={scene.image} alt="" width="72" height="54" />
              <span>{scene.name}</span>
            </button>
          ))}
        </div>
        <p className="shutters-caption" aria-live="polite">{scenes[selected].caption}</p>
        <button className="shutters-toggle" aria-expanded={open} onClick={() => setOpen(!open)}>{open ? "Close shutters" : "Open shutters"}</button>
      </div>
    </section>
  );
}
