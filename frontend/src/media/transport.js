import { registerMedia, claimMedia } from "./audio-focus.js";
// Native media lifecycle is confined here; React owns the rendered controls.
export class Transport {
  video = null;
  audio = null;
  resume = false;
  track = "original";
  audioOffset = 0;
  operation = 0;
  stopAt = null;
  bindAudio = (node) => {
    if (!node) return;
    this.audio = node;
    const release = registerMedia(node);
    return () => {
      release();
      this.audio = null;
    };
  };
  audioTime(value = this.video?.currentTime || 0) {
    return Math.max(0, value - this.audioOffset);
  }
  async play(stopAt = null) {
    if (!this.video) return;
    this.stopAt = stopAt;
    const operation = ++this.operation;
    claimMedia(this.video, this.audio);
    try {
      if (this.track !== "original" && this.audio) {
        this.audio.currentTime = this.audioTime();
        await this.audio.play();
        if (operation !== this.operation) return;
      }
      await this.video.play();
    } catch (error) {
      if (operation !== this.operation) return;
      this.pause();
      throw error;
    }
  }
  pause() {
    this.operation++;
    this.resume = false;
    this.video?.pause();
    this.audio?.pause();
    this.stopAt = null;
  }
  seek(value) {
    if (this.video) this.video.currentTime = value;
    if (this.audio && this.track !== "original") this.audio.currentTime = this.audioTime(value);
  }
  switchTrack(track, audioOffset = this.audioOffset) {
    this.audioOffset = Number(audioOffset) || 0;
    if (track === this.track) return;
    const resume = this.resume || (!!this.video && !this.video.paused);
    this.pause();
    this.resume = resume;
    this.track = track;
    if (this.video) this.video.muted = track !== "original";
    if (track === "original" && this.resume) {
      this.resume = false;
      return this.play();
    }
  }
  ready() {
    if (!this.video || !this.audio) return;
    this.audio.currentTime = this.audioTime();
    if (this.resume) {
      this.resume = false;
      return this.play();
    }
  }
  sync() {
    if (
      this.video &&
      this.stopAt !== null &&
      this.video.currentTime >= this.stopAt
    ) {
      this.pause();
      return;
    }
    if (
      this.video &&
      this.audio &&
      this.track !== "original" &&
      Math.abs(this.audio.currentTime - this.audioTime()) > 0.08
    )
      this.audio.currentTime = this.audioTime();
  }
}
