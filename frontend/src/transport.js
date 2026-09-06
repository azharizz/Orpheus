// Native media lifecycle is confined here; React owns the rendered controls.
export class Transport {
  video = null;
  audio = null;
  resume = false;
  track = "original";
  recording = false;
  bindVideo = (node) => {
    this.video = node;
    return () => {
      node.pause();
      this.video = null;
    };
  };
  bindAudio = (node) => {
    this.audio = node;
    return () => {
      node.pause();
      this.audio = null;
    };
  };
  async play() {
    if (!this.video) return;
    try {
      if (this.track !== "original" && this.audio) {
        this.audio.currentTime = this.video.currentTime;
        await this.audio.play();
      }
      await this.video.play();
    } catch (error) {
      this.pause();
      throw error;
    }
  }
  pause() {
    this.video?.pause();
    this.audio?.pause();
  }
  seek(value) {
    if (this.video) this.video.currentTime = value;
    if (this.audio && this.track !== "original") this.audio.currentTime = value;
  }
  switchTrack(track) {
    this.resume = !!this.video && !this.video.paused;
    this.pause();
    this.track = track;
    if (this.video) this.video.muted = track !== "original";
    if (track === "original" && this.resume) {
      this.resume = false;
      return this.play();
    }
  }
  ready() {
    if (!this.video || !this.audio) return;
    this.audio.currentTime = this.video.currentTime;
    if (this.resume) {
      this.resume = false;
      return this.play();
    }
  }
  sync() {
    if (
      this.video &&
      this.audio &&
      this.track !== "original" &&
      Math.abs(this.audio.currentTime - this.video.currentTime) > 0.08
    )
      this.audio.currentTime = this.video.currentTime;
  }
}
