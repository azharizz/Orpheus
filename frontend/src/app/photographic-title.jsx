import React, { useId, useState } from "react";
import step from "../assets/hero-step.webp";
import reel from "../assets/hero-reel.webp";
import microphone from "../assets/hero-microphone.webp";
import noise from "../assets/tv-static.webp";
import "../styles/photographic-title.css";

const scenes = [
  { image: step, y: -640, height: 1750, delay: "0s" },
  { image: reel, y: -90, height: 780, delay: "-6s" },
  { image: microphone, y: -150, height: 950, delay: "-3s" },
];

export function PhotographicTitle({ paused = false }) {
  const id = useId();
  const [gate, setGate] = useState({ x: 0, y: 0 });
  const trackPointer = (event) => {
    if (event.pointerType === "touch") return;
    const bounds = event.currentTarget.getBoundingClientRect();
    setGate({
      x: Math.round(((event.clientX - bounds.left) / bounds.width - 0.5) * 24),
      y: Math.round(((event.clientY - bounds.top) / bounds.height - 0.5) * 14),
    });
  };
  return (
    <section
      className="photographic-title"
      data-paused={paused}
      aria-label="Photographic title"
      style={{ "--gate-x": `${gate.x}px`, "--gate-y": `${gate.y}px` }}
      onPointerMove={trackPointer}
      onPointerLeave={() => setGate({ x: 0, y: 0 })}
    >
      <h1 className="title-accessible">ORPHEUS</h1>
      <svg className="title-stage" viewBox="0 0 1400 510" aria-hidden="true">
        <defs>
          <mask id={`${id}-letters`} maskUnits="userSpaceOnUse" x="0" y="0" width="1400" height="510">
            <text x="20" y="455" textLength="1360" lengthAdjust="spacingAndGlyphs" className="title-letters" fill="white">ORPHEUS</text>
          </mask>
        </defs>
        <g mask={`url(#${id}-letters)`}>
          <rect width="1400" height="510" fill="#201611" />
          {scenes.map((scene) => (
            <g key={scene.image} className="title-scene" style={{ "--scene-delay": scene.delay }}>
              <g className="title-gate">
                <image href={scene.image} y={scene.y} width="1400" height={scene.height} preserveAspectRatio="xMidYMid slice" className="title-photograph" />
              </g>
            </g>
          ))}
          <g className="title-interference">
            <image href={noise} x="-256" y="-256" width="1912" height="1022" preserveAspectRatio="none" className="title-noise" />
          </g>
        </g>
        <text x="20" y="455" textLength="1360" lengthAdjust="spacingAndGlyphs" className="title-letters title-outline">ORPHEUS</text>
      </svg>
    </section>
  );
}
