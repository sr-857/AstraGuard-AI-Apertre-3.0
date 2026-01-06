export enum AppMode {
  DEMO = 'DEMO',
  CODE = 'CODE',
  README = 'README'
}

export enum CameraMode {
  AUTO = 'AUTO',
  INTERACTIVE = 'INTERACTIVE'
}

export interface Point {
  x: number;
  y: number;
  label: number; // 1 for foreground, 0 for background
}

export interface GeneratedFile {
  filename: string;
  language: string;
  content: string;
}

export interface AnalysisResult {
  text: string;
  timestamp: number;
}