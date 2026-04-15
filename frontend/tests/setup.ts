import "@testing-library/jest-dom/vitest";

// Polyfill PointerEvent for jsdom
if (!global.PointerEvent) {
  global.PointerEvent = class PointerEvent extends Event {
    constructor(type, eventInitDict = {}) {
      super(type, eventInitDict);
      this.pointerId = eventInitDict.pointerId || 0;
      this.width = eventInitDict.width || 1;
      this.height = eventInitDict.height || 1;
      this.pressure = eventInitDict.pressure || 0;
      this.tiltX = eventInitDict.tiltX || 0;
      this.tiltY = eventInitDict.tiltY || 0;
      this.pointerType = eventInitDict.pointerType || '';
      this.isPrimary = eventInitDict.isPrimary || false;
    }
  } as any;
}