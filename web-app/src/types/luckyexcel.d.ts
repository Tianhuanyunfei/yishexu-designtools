declare module 'luckyexcel' {
  export default class LuckyExcel {
    static transformExcelToLucky(
      file: File | Blob,
      callback: (data: any) => void,
      errorCallback?: (error: any) => void
    ): void;
    init(file: File, callback: (data: any) => void): void;
  }
}
