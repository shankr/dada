const fs = require('fs');
const pdfParse = require('pdf-parse');

class PDFParser {
  constructor(filePath) {
    this.filePath = filePath;
  }
  
  async parse() {
    try {
      if (!fs.existsSync(this.filePath)) {
        throw new Error(`Resume file not found: ${this.filePath}`);
      }
      
      const dataBuffer = fs.readFileSync(this.filePath);
      const data = await pdfParse(dataBuffer);
      
      return {
        text: data.text,
        numpages: data.numpages
      };
    } catch (error) {
      throw new Error(`Error parsing PDF: ${error.message}`);
    }
  }
  
  async extractResumeData() {
    const parsed = await this.parse();
    
    return {
      rawText: parsed.text,
      numPages: parsed.numpages,
      cleanText: this.cleanText(parsed.text)
    };
  }
  
  cleanText(text) {
    return text
      .replace(/\n\n+/g, '\n')
      .replace(/\t/g, ' ')
      .replace(/ +/g, ' ')
      .trim();
  }
}

module.exports = PDFParser;