import express from 'express';
import nunjucks from 'nunjucks';
import multer from 'multer';
import path from 'path';
import { fileURLToPath } from 'url';
import { v4 as uuidv4 } from 'uuid';
import { extractTextFromFile } from './services/extractor.js';
import { analyzeResume } from './services/analyzer.js';
import { generateDocxReport } from './services/docx_exporter.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = 3000;

// Configure Multer memory storage for uploads
const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 10 * 1024 * 1024 } // 10MB
});

// Configure Nunjucks view engine
const templatesDir = path.join(__dirname, 'resume_analyzer/web/templates');
const env = nunjucks.configure(templatesDir, {
  autoescape: true,
  express: app,
  noCache: true
});

// Nunjucks Globals
env.addGlobal('url_for', (name, options) => {
  if (name === 'static') {
    return '/static/' + (options && options.path ? options.path : '');
  }
  return '/';
});

env.addGlobal('backend_build_state', () => ({
  build_id: 'v2.1.0-node',
  restart_required: false
}));

// Nunjucks Filters
env.addFilter('selectattr', (arr, attr, op, val) => {
  if (!Array.isArray(arr)) return [];
  return arr.filter(item => {
    if (op === 'equalto' || op === '==') return item && item[attr] === val;
    return item && Boolean(item[attr]);
  });
});

env.addFilter('round', (val, precision = 0) => {
  const factor = Math.pow(10, precision);
  return Math.round(Number(val || 0) * factor) / factor;
});

env.addFilter('int', (val) => parseInt(val || 0, 10));

env.addFilter('dump', (obj) => JSON.stringify(obj || {}));
env.addFilter('tojson', (obj) => nunjucks.runtime.markSafe(JSON.stringify(obj || {})));

env.addFilter('title', (val) => {
  if (val === null || val === undefined) return '';
  return String(val).replace(/\b\w/g, c => c.toUpperCase());
});

env.addFilter('items', (obj) => {
  if (!obj || typeof obj !== 'object') return [];
  return Object.entries(obj).map(([k, v]) => ({ key: k, value: v, 0: k, 1: v }));
});

env.addFilter('get', (obj, key, defaultVal = null) => {
  if (!obj || typeof obj !== 'object') return defaultVal;
  return obj && obj[key] !== undefined ? obj[key] : defaultVal;
});

// Serve static files
app.use('/static', express.static(path.join(__dirname, 'resume_analyzer/web/static')));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Security Headers Middleware
app.use((req, res, next) => {
  if (!req.path.startsWith('/static/')) {
    res.setHeader('X-Content-Type-Options', 'nosniff');
  }
  res.setHeader('Referrer-Policy', 'no-referrer');
  res.setHeader('X-Resume-Build', 'v2.1.0-node');
  next();
});

// In-Memory Job Store
const jobStore = new Map();

// Helper for formatting evidence
function formatEvidenceById(report) {
  const output = {};
  for (const ev of (report.evidence || [])) {
    let value = ev.value;
    if (value === null || value === undefined) {
      value = ev.kind === 'missing' ? 'Not present in the analyzed resume.' : 'Recorded without a display value.';
    }
    output[String(ev.id)] = {
      label: formatEvidenceLabel(String(ev.field_path || '')),
      value: value,
      kind: ev.kind || 'present'
    };
  }
  return output;
}

function formatEvidenceLabel(fieldPath) {
  const norm = fieldPath.toLowerCase();
  if (norm.startsWith('entities.contact.')) {
    const field = fieldPath.split('.').pop().replace(/_/g, ' ');
    return `Contact information: ${field.charAt(0).toUpperCase() + field.slice(1)}`;
  }
  if (norm.startsWith('entities.skills')) return 'Extracted skill';
  if (norm.startsWith('entities.summary')) return 'Professional summary';
  if (norm.startsWith('entities.experience')) return 'Experience entry';
  if (norm.startsWith('entities.projects')) return 'Project entry';
  if (norm.startsWith('entities.education')) return 'Education entry';
  if (norm.startsWith('entities.languages')) return 'Language entry';
  if (norm.includes('.heading')) return 'Section heading';
  if (norm.startsWith('extraction.layout_blocks')) return 'Document text sample';
  if (norm.startsWith('extraction.sections')) return 'Extracted resume section';
  if (norm.includes('quality')) return 'Extraction quality check';
  if (norm.includes('layout') || norm.includes('reading_order')) return 'Document layout check';
  return 'Resume evidence';
}

// Pages Routes
app.get('/', (req, res) => {
  res.render('index.html', {
    page_title: 'Resume Intelligence Platform',
    direction: 'ltr'
  });
});

app.get('/analyze', (req, res) => {
  res.render('analyze.html', {
    page_title: 'Analyze a resume',
    direction: 'ltr',
    settings: {
      max_upload_mb: 10,
      max_pages: 10,
      max_job_description_chars: 10000
    },
    models: {
      configured_provider: 'none',
      configured_model: 'gemma3:4b',
      fallback_available: true,
      ollama: { reachable: false, available_models: [] },
      transformers: { installed: false }
    }
  });
});

app.get('/results/:analysis_id', (req, res) => {
  const { analysis_id } = req.params;
  const record = jobStore.get(analysis_id);

  if (!record) {
    return res.status(404).render('error.html', {
      page_title: 'Analysis not found',
      direction: 'ltr',
      message: 'This temporary analysis does not exist or has expired.'
    });
  }

  if (record.status === 'failed') {
    return res.status(422).render('error.html', {
      page_title: 'Analysis could not be completed',
      direction: 'ltr',
      message: record.error?.message || 'Analysis failed.'
    });
  }

  if (record.status !== 'completed' || !record.result) {
    return res.render('progress.html', {
      page_title: 'Analysis in progress',
      direction: 'ltr',
      analysis_id
    });
  }

  const report = record.result;
  const language = report.target_role?.language || report.ats?.language || 'en';
  const direction = language === 'ar' ? 'rtl' : 'ltr';

  res.render('results.html', {
    page_title: 'Analysis results',
    direction,
    analysis_id,
    report,
    evidence_by_id: formatEvidenceById(report)
  });
});

// Robust Multer middleware that handles any field names and catches Multer errors gracefully
const handleFileUpload = (req, res, next) => {
  upload.any()(req, res, (err) => {
    if (err) {
      if (err instanceof multer.MulterError) {
        if (err.code === 'LIMIT_FILE_SIZE') {
          return res.status(400).json({
            error: { code: 'validation_error', message: 'File size exceeds maximum limit of 10MB.' }
          });
        }
        if (err.code === 'LIMIT_FIELD_NAME' || err.message?.includes('Field name missing')) {
          return res.status(400).json({
            error: { code: 'validation_error', message: 'Field name missing in upload request. Please select a valid resume file (PDF or DOCX).' }
          });
        }
        return res.status(400).json({
          error: { code: 'validation_error', message: `Upload error: ${err.message || 'Invalid upload parameters'}` }
        });
      }
      return res.status(400).json({
        error: { code: 'validation_error', message: err.message || 'Failed to process uploaded file.' }
      });
    }
    next();
  });
};

// API Routes
app.post('/api/analyses', handleFileUpload, async (req, res) => {
  try {
    const files = req.files || [];
    
    // Find resume file: preferentially with fieldname 'resume', or 'file', 'document', 'resume_file', or first file
    let resumeFile = files.find(f => f.fieldname === 'resume')
      || files.find(f => ['file', 'document', 'resume_file', 'upload'].includes(f.fieldname))
      || files.find(f => f.fieldname !== 'job_description_file' && f.fieldname !== 'job_description')
      || files[0];

    if (!resumeFile) {
      return res.status(400).json({
        error: { code: 'validation_error', message: 'Please select a resume file (PDF or DOCX).' }
      });
    }

    // Find job description file if uploaded
    let jobDescFile = files.find(f => f.fieldname === 'job_description_file' || f.fieldname === 'job_description');
    if (!jobDescFile && files.length > 1) {
      jobDescFile = files.find(f => f !== resumeFile);
    }

    let jobDescText = req.body?.job_description_text || '';
    if (jobDescFile && jobDescFile.buffer) {
      jobDescText = jobDescFile.buffer.toString('utf-8');
    }

    const options = {
      enable_target_role: req.body.enable_target_role !== 'false',
      enable_recommendations: req.body.enable_recommendations !== 'false',
      enable_ats: req.body.enable_ats !== 'false',
      enable_job_match: req.body.enable_job_match !== 'false',
      enable_rewrites: req.body.enable_rewrites === 'true',
      enable_ocr: req.body.enable_ocr !== 'false',
      ai_provider: req.body.ai_provider || 'none',
      ai_model: req.body.ai_model || 'gemma3:4b',
      output_language: req.body.output_language || 'auto',
      job_description_text: jobDescText,
      bullet_rewrite_count: parseInt(req.body.bullet_rewrite_count || '20', 10)
    };

    const extracted = await extractTextFromFile(resumeFile.buffer, resumeFile.originalname, resumeFile.mimetype);
    const report = analyzeResume(extracted, options, resumeFile.originalname);

    const id = uuidv4();
    const record = {
      id,
      status: 'completed',
      stage: 'completed',
      result: report,
      created_at: new Date()
    };

    jobStore.set(id, record);

    res.status(202).json({
      analysis_id: id,
      status: 'completed',
      status_url: `/api/analyses/${id}`,
      result_url: `/api/analyses/${id}/result`,
      page_url: `/results/${id}`
    });
  } catch (err) {
    console.error('Error starting analysis:', err);
    res.status(500).json({
      error: { code: 'internal_error', message: 'Failed to analyze the uploaded document.' }
    });
  }
});

app.get('/api/analyses/:analysis_id', (req, res) => {
  const record = jobStore.get(req.params.analysis_id);
  if (!record) {
    return res.status(404).json({ error: { message: 'Analysis not found or expired.' } });
  }
  res.json({
    id: record.id,
    status: record.status,
    stage: record.stage
  });
});

app.get('/api/analyses/:analysis_id/result', (req, res) => {
  const record = jobStore.get(req.params.analysis_id);
  if (!record || !record.result) {
    return res.status(404).json({ error: { message: 'Result not available.' } });
  }
  res.json(record.result);
});

app.get('/api/analyses/:analysis_id/download', (req, res) => {
  const record = jobStore.get(req.params.analysis_id);
  if (!record || !record.result) {
    return res.status(404).json({ error: { message: 'Result not available.' } });
  }
  const payload = JSON.stringify(record.result, null, 2);
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Content-Disposition', `attachment; filename="analysis-${record.id}.json"`);
  res.send(payload);
});

app.get('/api/analyses/:analysis_id/download-docx', async (req, res) => {
  const record = jobStore.get(req.params.analysis_id);
  if (!record || !record.result) {
    return res.status(404).json({ error: { message: 'Result not available.' } });
  }
  const template = req.query.template || 'single_column';
  try {
    const buffer = await generateDocxReport(record.result, template);
    const filename = `optimized-resume-${template}-${record.id}.docx`;
    res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document');
    res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
    res.send(buffer);
  } catch (err) {
    console.error('Error generating DOCX:', err);
    res.status(500).json({ error: { message: 'Failed to generate Word document.' } });
  }
});

app.delete('/api/analyses/:analysis_id', (req, res) => {
  jobStore.delete(req.params.analysis_id);
  res.status(204).send();
});

app.get('/api/health', (req, res) => {
  res.json({
    status: 'ok',
    version: '2.1.0-node',
    uptime: process.uptime(),
    build: {
      build_id: 'v2.1.0-node',
      restart_required: false
    }
  });
});

app.get('/api/system', (req, res) => {
  res.json({
    capabilities: {
      pdf_parsing: true,
      docx_parsing: true,
      ocr: false,
      ai_models: false
    }
  });
});

app.get('/api/models', (req, res) => {
  res.json({
    configured_provider: 'none',
    configured_model: null,
    fallback_available: true,
    ollama: { reachable: false, available_models: [] },
    transformers: { installed: false }
  });
});

// Global Error Handler
app.use((err, req, res, next) => {
  if (err instanceof multer.MulterError) {
    return res.status(400).json({
      error: { code: 'validation_error', message: `Upload error: ${err.message}` }
    });
  }
  console.error('Unhandled server error:', err);
  if (res.headersSent) {
    return next(err);
  }
  res.status(500).json({
    error: { code: 'internal_error', message: err.message || 'Internal server error occurred.' }
  });
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`Resume Intelligence Platform running on http://0.0.0.0:${PORT}`);
});
