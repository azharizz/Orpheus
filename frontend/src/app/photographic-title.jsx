import React, { useId } from "react";
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
  return (
    <section className="photographic-title" data-paused={paused} aria-label="Photographic title">
      <h1 className="title-accessible">ORPHEUS</h1>
      <svg className="title-stage" viewBox="0 0 1400 510" aria-hidden="true">
        <defs>
          <mask id={`${id}-letters`} maskUnits="userSpaceOnUse" x="0" y="0" width="1400" height="510">
            <text x="20" y="455" textLength="1360" lengthAdjust="spacingAndGlyphs" className="title-letters" fill="white">ORPHEUS</text>
          </mask>
          <pattern id={`${id}-noise`} width="256" height="256" patternUnits="userSpaceOnUse">
            <image href={noise} width="256" height="256" />
          </pattern>
        </defs>
        <g mask={`url(#${id}-letters)`}>
          <rect width="1400" height="510" fill="#b58c6a" />
          {scenes.map((scene) => (
            <g key={scene.image} className="title-scene" style={{ "--scene-delay": scene.delay }}>
              <image href={scene.image} y={scene.y} width="1400" height={scene.height} preserveAspectRatio="xMidYMid slice" className="title-photograph" />
            </g>
          ))}
          <g className="title-interference">
            <rect x="-256" y="-256" width="1912" height="1022" fill={`url(#${id}-noise)`} className="title-noise" />
          </g>
        </g>
        <text x="20" y="455" textLength="1360" lengthAdjust="spacingAndGlyphs" className="title-letters title-outline">ORPHEUS</text>
      </svg>
    </section>
  );
}
