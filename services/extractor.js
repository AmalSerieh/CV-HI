import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const pdfParse = require('pdf-parse');
const mammoth = require('mammoth');

export async function extractTextFromFile(buffer, filename, mimetype) {
  const ext = (filename || '').split('.').pop().toLowerCase();
  let text = '';
  let pageCount = 1;
  let engine = 'plain_text';

  if (ext === 'pdf' || mimetype === 'application/pdf') {
    engine = 'pdf_parse';
    try {
      const data = await pdfParse(buffer);
      text = data.text || '';
      pageCount = data.numpages || 1;
    } catch (err) {
      console.warn('PDF parsing fallback to raw string:', err.message);
      text = buffer.toString('utf-8');
    }
  } else if (ext === 'docx' || (mimetype && mimetype.includes('word'))) {
    engine = 'mammoth_docx';
    try {
      const result = await mammoth.extractRawText({ buffer });
      text = result.value || '';
    } catch (err) {
      console.warn('DOCX parsing fallback to raw string:', err.message);
      text = buffer.toString('utf-8');
    }
  } else {
    text = buffer.toString('utf-8');
  }

  // Clean non-printable characters or weird binary artifacts if any
  text = text.replace(/[\x00-\x08\x0B\x0C\x0E-\x1F]/g, '');

  return {
    text: text.trim(),
    pageCount: Math.max(1, pageCount),
    charCount: text.length,
    engine,
  };
}
