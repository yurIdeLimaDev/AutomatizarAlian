export type Mode = 'old' | 'suelane';
export interface PdfRecord {
  segurado: string;
  inicio_vig: string;
  apolice: string;
}
export interface Result {
  filename: string;
  output: string | null;
  pdfCount: number;
  spreadsheetCount: number;
  matchedCount: number;
  anomalies: number;
  total: number;
  warnings: string[];
  notFound: PdfRecord[];
}
export interface InputFile {
  name: string;
  bytes: ArrayBuffer;
}
export type Request = { mode: Mode; pdfs: InputFile[]; sheets: InputFile[] };
export type Response =
  | { type: 'progress'; message: string }
  | { type: 'done'; result: Result; bytes: Uint8Array | null }
  | { type: 'error'; message: string };
