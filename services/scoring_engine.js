/**
 * scoring_engine.js
 * Comprehensive modular scoring engine for Resume Intelligence Platform
 * Academic References:
 * - Google re:Work (XYZ Formula)
 * - Resume Worded (Action Verbs, Impact & Quantified Metrics)
 * - Purdue OWL, Sabbar & ThinkIN (ATS & Contact Standards)
 * - Workday, Greenhouse & Taleo Resume Guide (Section Quality)
 * - Taqdeem, Jobseeker & Basmah Aljuhani (Skills Intrinsic Quality)
 */

export class ContactScorer {
  /**
   * Evaluates contact information (10 points max)
   */
  constructor(parsedJson) {
    this.data = parsedJson || {};
    this.contactData = this.data.contact || (this.data.entities && this.data.entities.contact) || {};
    this.diagnostics = this.data.diagnostics || {};
    this.score = 0.0;
    this.details = {};
    this.missingElements = [];
    this.appliedDeductions = [];
  }

  evaluate() {
    this.score = 0.0;
    this.details = {};
    this.missingElements = [];
    this.appliedDeductions = [];

    // 1. Full Name (+2.0)
    const name = this.contactData.name;
    if (name && String(name).trim().toLowerCase() !== 'none' && String(name).trim().toLowerCase() !== 'null' && String(name).trim() !== '') {
      this.score += 2.0;
      this.details["Name"] = { status: "Found", value: name, points: 2.0 };
    } else {
      this.missingElements.push("Full Name");
      this.details["Name"] = { status: "Missing", value: null, points: 0.0 };
    }

    // 2. Phone Number (+2.0)
    const phone = this.contactData.phone;
    if (phone && String(phone).trim() !== '') {
      this.score += 2.0;
      this.details["Phone"] = { status: "Found", value: phone, points: 2.0 };
    } else {
      this.missingElements.push("Phone Number");
      this.details["Phone"] = { status: "Missing", value: null, points: 0.0 };
    }

    // 3. Email Address (+2.0)
    const email = this.contactData.email;
    if (email && String(email).includes('@')) {
      this.score += 2.0;
      this.details["Email"] = { status: "Found", value: email, points: 2.0 };
    } else {
      this.missingElements.push("Email Address");
      this.details["Email"] = { status: "Missing", value: null, points: 0.0 };
    }

    // 4. LinkedIn Profile (+2.0)
    const linkedin = this.contactData.linkedin;
    if (linkedin && String(linkedin).trim() !== '') {
      this.score += 2.0;
      this.details["LinkedIn"] = { status: "Found", value: linkedin, points: 2.0 };
    } else {
      this.missingElements.push("LinkedIn Profile");
      this.details["LinkedIn"] = { status: "Missing", value: null, points: 0.0 };
    }

    // 5. Location (+2.0)
    const location = this.contactData.location || this.contactData.candidate_location;
    if (location && String(location).trim() !== '') {
      this.score += 2.0;
      this.details["Location"] = { status: "Found", value: location, points: 2.0 };
    } else {
      this.missingElements.push("Location (City, Country)");
      this.details["Location"] = { status: "Missing", value: null, points: 0.0 };
    }

    // Apply Deductions
    const textWarnings = (this.data.text_extraction && this.data.text_extraction.warnings) || [];
    const resolvedWarnings = (this.data.legacy_extraction_quality && this.data.legacy_extraction_quality.resolved_warnings) || [];
    const allWarnings = [...textWarnings, ...resolvedWarnings];

    const headerFooterDetected = allWarnings.some(w => String(w).includes("removed_repeated_header_footer_blocks") || String(w).includes("header_footer"));
    if (headerFooterDetected) {
      this.score -= 1.5;
      this.appliedDeductions.push({
        section: "Contact Information",
        reason: "Contact info potentially inside Header/Footer (ATS parsing risk).",
        penalty: -1.5,
        reference: "ThinkIN ATS Guide"
      });
    }

    const layoutDiag = this.diagnostics.layout || {};
    const textBoxCount = layoutDiag.text_box_count || 0;
    if (textBoxCount > 0) {
      this.score -= 1.5;
      this.appliedDeductions.push({
        section: "Contact Information",
        reason: `Detected ${textBoxCount} Text Box(es) which break ATS parsing.`,
        penalty: -1.5,
        reference: "Resumly Formatting Best Practices"
      });
    }

    if (this.score < 0) this.score = 0.0;

    return {
      section_name: "Contact Information",
      section_name_ar: "معلومات التواصل",
      score: Math.round(this.score * 10) / 10,
      max_score: 10.0,
      percentage: Math.round((this.score / 10.0) * 100),
      status: this.score >= 8.0 ? "Excellent" : this.score >= 5.0 ? "Good" : "Needs Improvement",
      status_ar: this.score >= 8.0 ? "ممتاز" : this.score >= 5.0 ? "جيد" : "يحتاج تحسين",
      elements: this.details,
      missing_elements: this.missingElements,
      penalties_applied: this.appliedDeductions,
      academic_references: [
        "[Purdue OWL] Contact Information Formatting guidelines.",
        "[Resume Worded] ATS passability and required contact formats.",
        "[Sabbar] Middle East & ATS CV standards.",
        "[ThinkIN] ATS parsing risks with Headers/Footers."
      ]
    };
  }
}

export class SectionScorer {
  /**
   * Evaluates Section Quality & Structure (10 points max)
   */
  constructor(parsedJson) {
    this.data = parsedJson || {};
    this.sectionsData = this.data.sections || {};
    this.foundSections = this.sectionsData.found_sections || Object.keys(this.data.sections || {});
    this.missingSections = this.sectionsData.missing_required || [];
    this.layout = (this.data.text_extraction && this.data.text_extraction.layout) || "single_column";
    this.score = 0.0;
    this.details = {};
    this.missingElements = [];
    this.appliedDeductions = [];
  }

  evaluate() {
    this.score = 0.0;
    this.details = {};
    this.missingElements = [];
    this.appliedDeductions = [];

    const coreSections = {
      summary: "Professional Summary",
      experience: "Work Experience",
      education: "Education Background",
      skills: "Technical/Soft Skills"
    };

    for (const [secKey, secLabel] of Object.entries(coreSections)) {
      const isPresent = this.foundSections.includes(secKey) || (this.data[secKey] && Object.keys(this.data[secKey]).length > 0);
      if (isPresent) {
        this.score += 2.5;
        this.details[secLabel] = { status: "Found", points: 2.5 };
      } else {
        this.missingElements.push(secLabel);
        this.details[secLabel] = { status: "Missing", points: 0.0 };
      }
    }

    if (this.layout !== "single_column" && this.layout !== "unknown") {
      this.score -= 2.0;
      this.appliedDeductions.push({
        section: "Section Structure",
        reason: `Detected layout: '${this.layout}'. ATS systems prefer 'single_column'.`,
        penalty: -2.0,
        reference: "Workday, Greenhouse & Taleo Resume Guide"
      });
    }

    const sectionQuality = this.data.section_quality || {};
    const invalidSections = sectionQuality.missing_or_invalid || [];
    if (invalidSections.length > 0) {
      this.score -= 1.5;
      this.appliedDeductions.push({
        section: "Section Structure",
        reason: `Non-standard or unreadable section headers detected: ${invalidSections.join(", ")}.`,
        penalty: -1.5,
        reference: "Standard Resume Format Guidelines"
      });
    }

    if (this.score < 0) this.score = 0.0;

    return {
      section_name: "Section Quality & Structure",
      section_name_ar: "جودة وبنية الأقسام",
      score: Math.round(this.score * 10) / 10,
      max_score: 10.0,
      percentage: Math.round((this.score / 10.0) * 100),
      status: this.score >= 8.0 ? "Excellent" : this.score >= 5.0 ? "Good" : "Needs Improvement",
      status_ar: this.score >= 8.0 ? "ممتاز" : this.score >= 5.0 ? "جيد" : "يحتاج تحسين",
      elements: this.details,
      missing_elements: this.missingElements,
      penalties_applied: this.appliedDeductions,
      academic_references: [
        "[Workday, Greenhouse & Taleo Resume Guide] Single-column format and standard headers requirement.",
        "[Resume Worded] Section Quality and Structure score validation.",
        "[SHRM & CIMS] Standard formatting guidelines for recruiters."
      ]
    };
  }
}

export class SkillsScorer {
  /**
   * Evaluates Skills Quality (Intrinsic Evaluation - 100 points max)
   */
  constructor(parsedJson) {
    this.data = parsedJson || {};
    this.skillsData = this.data.skills || {};
    this.skills = Array.isArray(this.data.skills) ? this.data.skills : (this.skillsData.all_skills || this.data.entities?.skills || []);
    this.hardSkills = this.skillsData.hard_skills || this.skills;
    this.sectionsData = this.data.sections?.sections || {};
    this.experienceData = this.data.experience || {};
    this.totalScore = 0.0;
    this.details = {};
    this.appliedDeductions = [];
    this.missingElements = [];

    this.fluffWords = new Set([
      "working under pressure", "hard worker", "computer skills", "fast learner",
      "ms office", "microsoft office", "internet", "typing", "multitasking",
      "العمل تحت الضغط", "إجادة الحاسب", "العمل بروح الفريق", "سرعة التعلم", "تعدد المهام"
    ]);
  }

  evaluate() {
    this.totalScore = 0.0;
    this.details = {};
    this.appliedDeductions = [];
    this.missingElements = [];

    const allSkillsList = Array.isArray(this.skills) ? this.skills : [];
    const count = allSkillsList.length;

    // 1. Specificity & Naming (30 pts max)
    let specScore = 20.0;
    if (this.hardSkills.length >= 3) specScore += 10.0;

    const fluffFound = [];
    for (const skill of allSkillsList) {
      if (this.fluffWords.has(String(skill).toLowerCase().trim())) {
        specScore -= 10.0;
        fluffFound.push(skill);
      }
    }
    specScore = Math.max(0.0, Math.min(30.0, specScore));
    this.totalScore += specScore;

    if (fluffFound.length > 0) {
      this.appliedDeductions.push({
        section: "Skills",
        reason: `Found generic fluff skill phrases: ${fluffFound.join(', ')}`,
        penalty: -10.0 * fluffFound.length,
        reference: "Taqdeem.net Skills Guide"
      });
    }

    this.details["Specificity & Naming"] = {
      score: specScore,
      max: 30.0,
      fluff_words_penalized: fluffFound
    };

    // 2. Structure & Categorization (25 pts max)
    let structScore = 0.0;
    const skillsSection = this.sectionsData.skills || {};
    const heading = skillsSection.heading || "";
    if (heading && /skill|مهار/i.test(heading)) structScore += 5.0;
    if (this.skillsData.categorized_count > 0 || (typeof this.skillsData === 'object' && !Array.isArray(this.skillsData) && Object.keys(this.skillsData).length > 2)) {
      structScore += 10.0;
    }
    if (count > 0) structScore += 10.0;

    this.totalScore += structScore;
    this.details["Structure & Categorization"] = { score: structScore, max: 25.0 };

    // 3. Focus & Brevity (20 pts max)
    let focusScore = 0.0;
    if (count >= 6 && count <= 12) {
      focusScore = 20.0;
    } else if (count >= 13 && count <= 18) {
      focusScore = 10.0;
    } else {
      focusScore = 0.0;
      const penaltyVal = count > 18 ? -20.0 : -10.0;
      this.appliedDeductions.push({
        section: "Skills",
        reason: `Skill count (${count}) is outside the optimal range (6-12).`,
        penalty: penaltyVal,
        reference: "Basmah Aljuhani & Taqdeem CV Guide"
      });
    }
    this.totalScore += focusScore;
    this.details["Focus & Brevity"] = { score: focusScore, max: 20.0, total_skills: count };

    // 4. Evidence in Experience / Projects (25 pts max)
    const expText = String(this.experienceData.raw_experience_text || JSON.stringify(this.experienceData)).toLowerCase();
    const projText = String(this.data.projects?.raw_projects_text || JSON.stringify(this.data.projects || [])).toLowerCase();
    const combinedText = expText + " " + projText;

    let provenSkills = [];
    if (count > 0 && combinedText.trim().length > 0) {
      for (const sk of allSkillsList) {
        if (combinedText.includes(String(sk).toLowerCase())) {
          provenSkills.push(sk);
        }
      }
      const ratio = provenSkills.length / count;
      const evidenceScore = Math.round(ratio * 25.0 * 10) / 10;
      this.totalScore += evidenceScore;
      this.details["Evidence in Experience"] = { score: evidenceScore, max: 25.0, proven_skills_count: provenSkills.length };
    } else {
      this.details["Evidence in Experience"] = { score: 0.0, max: 25.0, proven_skills_count: 0 };
    }

    if (count < 6) {
      this.missingElements.push("Diverse Technical Skills (6-12 recommended)");
    }

    this.totalScore = Math.max(0.0, Math.min(100.0, this.totalScore));

    return {
      section_name: "Skills Quality (Intrinsic Evaluation)",
      section_name_ar: "المهارات والتقنيات",
      score: Math.round(this.totalScore * 10) / 10,
      max_score: 100.0,
      percentage: Math.round(this.totalScore),
      status: this.totalScore >= 85.0 ? "Excellent" : this.totalScore >= 65.0 ? "Good" : "Needs Improvement",
      status_ar: this.totalScore >= 85.0 ? "ممتاز" : this.totalScore >= 65.0 ? "جيد" : "يحتاج تحسين",
      elements: this.details,
      missing_elements: this.missingElements,
      penalties_applied: this.appliedDeductions,
      academic_references: [
        "[Taqdeem.net] Specificity & Naming: Write technical skills explicitly and remove fluff.",
        "[Jobseeker & Resumk] Structure & Categorization: Clear headings, categorized into Hard/Soft, bullet points.",
        "[Taqdeem & Basmah Aljuhani] Focus & Brevity: Ideal count is 6-12 skills.",
        "[Taqdeem & ETFC-KSA] Evidence in Experience: Skills must be proven in experience bullet points."
      ]
    };
  }
}

export class ExperienceScorer {
  /**
   * Evaluates Experience Quality (Impact & Verbs - 100 points max)
   */
  constructor(parsedJson) {
    this.data = parsedJson || {};
    this.experienceData = this.data.experience || {};
    this.experiences = Array.isArray(this.data.experience)
      ? this.data.experience
      : (this.experienceData.experiences || this.data.entities?.experience || []);

    this.weakStarters = new Set([
      "helped", "assisted", "worked", "handled", "participated",
      "responsible", "duties", "tasked", "doing", "did", "made",
      "ساعدت", "عملت", "كانت مسؤولياتي", "من مهامي", "شاركت"
    ]);

    this.irregularPastVerbs = new Set([
      "led", "built", "grew", "ran", "drove", "won", "taught", "brought",
      "oversaw", "undertook", "wrote", "held", "kept", "gave", "found", "did"
    ]);

    this.totalScore = 0.0;
    this.details = {};
    this.appliedDeductions = [];
    this.missingElements = [];
  }

  evaluate() {
    this.totalScore = 0.0;
    this.details = {};
    this.appliedDeductions = [];
    this.missingElements = [];

    const expList = Array.isArray(this.experiences) ? this.experiences : [];
    if (expList.length === 0) {
      this.missingElements.push("Work Experience Section");
      this.appliedDeductions.push({
        section: "Experience",
        reason: "No work experience entries found.",
        penalty: -100.0,
        reference: "Purdue OWL Career Guidelines"
      });
      return {
        section_name: "Experience Quality (Impact & Verbs)",
        section_name_ar: "جودة الخبرات والإنتاجية",
        score: 0.0,
        max_score: 100.0,
        percentage: 0,
        status: "Needs Improvement",
        status_ar: "يحتاج تحسين",
        elements: {},
        missing_elements: this.missingElements,
        penalties_applied: this.appliedDeductions
      };
    }

    let totalBullets = 0;
    let actionVerbBullets = 0;
    let pastTenseBullets = 0;
    let weakBullets = 0;
    let missingBulletsRoles = 0;

    for (const exp of expList) {
      const bullets = exp.bullets || exp.responsibilities || [];
      totalBullets += bullets.length;
      if (!bullets || bullets.length === 0) missingBulletsRoles++;

      for (const bullet of bullets) {
        const text = String(bullet).trim();
        const words = text.match(/\b[A-Za-zÀ-ÿ0-9_]+\b/g) || [];
        if (words.length === 0) continue;

        const firstWord = words[0].toLowerCase();

        if (this.weakStarters.has(firstWord) || text.toLowerCase().includes("responsible for")) {
          weakBullets++;
        } else {
          actionVerbBullets++;
        }

        if (firstWord.endsWith("ed") || this.irregularPastVerbs.has(firstWord)) {
          pastTenseBullets++;
        }
      }
    }

    // 1. Action Verbs Usage (40 max)
    let actionScore = 0.0;
    if (totalBullets > 0) {
      actionScore = Math.round((actionVerbBullets / totalBullets) * 40.0 * 10) / 10;
    }
    this.totalScore += actionScore;
    this.details["Action Verbs Usage"] = { score: actionScore, max: 40.0, strong_action_verbs_found: actionVerbBullets };

    // 2. Past Tense (30 max)
    let pastScore = 0.0;
    if (totalBullets > 0) {
      const ratio = pastTenseBullets / totalBullets;
      const adjustedRatio = Math.min(1.0, ratio / 0.7);
      pastScore = Math.round(adjustedRatio * 30.0 * 10) / 10;
    }
    this.totalScore += pastScore;
    this.details["Past Tense (Achievements)"] = { score: pastScore, max: 30.0, past_tense_bullets_found: pastTenseBullets };

    // 3. Structure & Bullet Points (30 max)
    let structScore = Math.max(0.0, 30.0 - (missingBulletsRoles * 10.0));
    this.totalScore += structScore;
    this.details["Structure & Bullet Points"] = { score: structScore, max: 30.0, roles_missing_bullets: missingBulletsRoles };

    // Deductions for weak bullets
    if (weakBullets > 0) {
      const penalty = Math.min(20.0, weakBullets * 5.0);
      this.totalScore -= penalty;
      this.appliedDeductions.push({
        section: "Experience",
        reason: `Found ${weakBullets} bullet(s) starting with weak/passive words (e.g., 'Helped', 'Responsible for').`,
        penalty: -penalty,
        reference: "Resume Worded (Impact Analysis)"
      });
    }

    this.totalScore = Math.max(0.0, Math.min(100.0, this.totalScore));

    return {
      section_name: "Experience Quality (Impact & Verbs)",
      section_name_ar: "الخبرات العملية",
      score: Math.round(this.totalScore * 10) / 10,
      max_score: 100.0,
      percentage: Math.round(this.totalScore),
      status: this.totalScore >= 85.0 ? "Excellent" : this.totalScore >= 65.0 ? "Good" : "Needs Improvement",
      status_ar: this.totalScore >= 85.0 ? "ممتاز" : this.totalScore >= 65.0 ? "جيد" : "يحتاج تحسين",
      elements: this.details,
      missing_elements: this.missingElements,
      penalties_applied: this.appliedDeductions,
      academic_references: [
        "[Resume Worded] Impact & Action Verbs: Bullet points must start with strong action verbs.",
        "[Resume Worded] Past Tense: Achievements and past responsibilities should be formulated in past tense.",
        "[Standard Industry Practices] Structure: Experience must be formatted as bullet points, not paragraphs."
      ]
    };
  }
}

export class AchievementsScorer {
  /**
   * Evaluates Achievements & Quantification (XYZ Formula - 100 points max)
   * References: Google re:Work (XYZ Formula), Resume Worded (Impact)
   */
  constructor(parsedJson) {
    this.data = parsedJson || {};
    this.evidenceData = this.data.evidence_reconciliation || {};
    this.metrics = this.evidenceData.document_metrics || this.extractMetricsFromData(this.data);
    this.experienceData = this.data.experience || {};
    this.experiences = Array.isArray(this.data.experience) ? this.data.experience : (this.experienceData.experiences || []);
    this.totalScore = 0.0;
    this.details = {};
    this.appliedDeductions = [];
  }

  extractMetricsFromData(data) {
    const list = [];
    const metricRegex = /(\d+(?:\.\d+)?%|\$\d+(?:\,\d+)?|\b\d+\b\s*(?:users|clients|projects|increase|growth|revenue|reduction)?)/gi;
    const strData = JSON.stringify(data);
    const matches = strData.match(metricRegex) || [];
    for (const m of matches) {
      list.push({ metric_type: m.includes('%') ? 'percentage' : m.includes('$') ? 'currency' : 'quantity', value: m });
    }
    return list;
  }

  evaluate() {
    this.totalScore = 0.0;
    this.details = {};
    this.appliedDeductions = [];

    const metricCount = this.metrics.length;

    // 1. Metrics Volume (40 max)
    const volumeScore = Math.min(40.0, metricCount * 8.0);
    this.totalScore += volumeScore;
    this.details["Metrics Volume (Quantification)"] = {
      score: volumeScore,
      max: 40.0,
      metrics_found: metricCount
    };

    // 2. Metrics Distribution Across Roles (30 max)
    let distScore = 0.0;
    const totalRoles = this.experiences.length;
    let rolesWithMetrics = 0;
    for (const exp of this.experiences) {
      const bullets = exp.bullets || exp.responsibilities || [];
      if (bullets.some(b => /\d+%|\$\d+|\b\d+\b/.test(String(b)))) {
        rolesWithMetrics++;
      }
    }
    if (totalRoles > 0) {
      distScore = Math.round((rolesWithMetrics / totalRoles) * 30.0 * 10) / 10;
    } else if (metricCount > 0) {
      distScore = 30.0;
    }
    this.totalScore += distScore;
    this.details["Metrics Distribution Across Roles"] = { score: distScore, max: 30.0, roles_with_metrics: rolesWithMetrics, total_roles: totalRoles };

    // 3. Metric Types Diversity (30 max)
    const foundTypes = new Set();
    for (const m of this.metrics) {
      if (m.metric_type) foundTypes.add(m.metric_type);
    }
    const diversityScore = Math.min(30.0, foundTypes.size * 10.0);
    this.totalScore += diversityScore;
    this.details["Metric Types Diversity"] = { score: diversityScore, max: 30.0, types_found: Array.from(foundTypes) };

    // Deductions: multiple experiences but zero metrics
    if (totalRoles >= 2 && metricCount === 0) {
      this.totalScore -= 20.0;
      this.appliedDeductions.push({
        section: "Achievements",
        reason: "Resume lists multiple experiences but contains ZERO quantified achievements.",
        penalty: -20.0,
        reference: "Google re:Work XYZ Formula - Missing 'Measured by [Y]'"
      });
    }

    this.totalScore = Math.max(0.0, Math.min(100.0, this.totalScore));

    return {
      section_name: "Achievements & Quantification (XYZ Formula)",
      section_name_ar: "الإنجازات والأرقام الكمية",
      score: Math.round(this.totalScore * 10) / 10,
      max_score: 100.0,
      percentage: Math.round(this.totalScore),
      status: this.totalScore >= 80.0 ? "Excellent" : this.totalScore >= 50.0 ? "Good" : "Needs Improvement",
      status_ar: this.totalScore >= 80.0 ? "ممتاز" : this.totalScore >= 50.0 ? "جيد" : "يحتاج تحسين",
      elements: this.details,
      missing_elements: metricCount === 0 ? ["Quantified Impact Metrics (% / $ / Scale)"] : [],
      penalties_applied: this.appliedDeductions,
      academic_references: [
        "[Google re:Work] XYZ Formula: Accomplished [X] as measured by [Y], by doing [Z].",
        "[Resume Worded] Quantified Impact: Strong resumes use numbers, percentages, and currencies to prove scale."
      ]
    };
  }
}

export class ProjectsScorer {
  /**
   * Evaluates Projects Section (100 points max)
   */
  constructor(parsedJson) {
    this.data = parsedJson || {};
    this.projectsData = this.data.projects || {};
    this.projectsList = Array.isArray(this.data.projects)
      ? this.data.projects
      : (this.projectsData.projects || this.data.entities?.projects || []);
    this.rawText = String(this.projectsData.raw_projects_text || JSON.stringify(this.projectsList));
    this.projectCount = this.projectsList.length || (this.rawText.trim().length > 10 ? 1 : 0);

    this.totalScore = 0.0;
    this.details = {};
    this.appliedDeductions = [];
    this.missingElements = [];
  }

  evaluate() {
    this.totalScore = 0.0;
    this.details = {};
    this.appliedDeductions = [];
    this.missingElements = [];

    if (!this.rawText.trim() || this.projectCount === 0) {
      this.missingElements.push("Key Projects & Portfolio Showcase");
      this.appliedDeductions.push({
        section: "Projects",
        reason: "No Projects section detected.",
        penalty: -20.0,
        reference: "Tech Industry Standards (Proof of Work)"
      });
      return {
        section_name: "Projects Evaluation",
        section_name_ar: "المشاريع والأعمال",
        score: 0.0,
        max_score: 100.0,
        percentage: 0,
        status: "Needs Improvement",
        status_ar: "يحتاج تحسين",
        elements: {},
        missing_elements: this.missingElements,
        penalties_applied: this.appliedDeductions
      };
    }

    // 1. Presence & Volume (40 max)
    let volumeScore = this.projectCount >= 2 ? 40.0 : (this.projectCount === 1 ? 20.0 : 0.0);
    this.totalScore += volumeScore;
    this.details["Presence & Volume"] = { score: volumeScore, max: 40.0, projects_count: this.projectCount };

    // 2. Proof of Work (Links) (30 max)
    let linksScore = 0.0;
    const urls = this.rawText.match(/(https?:\/\/\S+|www\.\S+|github\.com\/\S+)/gi) || [];
    if (urls.length > 0) {
      linksScore = 30.0;
    } else {
      this.appliedDeductions.push({
        section: "Projects",
        reason: "Projects mentioned but NO links (GitHub, Live URL) provided to verify the work.",
        penalty: -15.0,
        reference: "Tech Resume Guidelines (Proof of Work)"
      });
    }
    this.totalScore += linksScore;
    this.details["Proof of Work (Links)"] = { score: linksScore, max: 30.0, links_found: urls };

    // 3. Description Quality (30 max)
    const wordCount = this.rawText.split(/\s+/).length;
    let descScore = wordCount > 40 ? 30.0 : (wordCount > 15 ? 15.0 : 5.0);
    this.totalScore += descScore;
    this.details["Description Quality & Details"] = { score: descScore, max: 30.0, word_count: wordCount };

    this.totalScore = Math.max(0.0, Math.min(100.0, this.totalScore));

    return {
      section_name: "Projects Evaluation",
      section_name_ar: "المشاريع والأعمال",
      score: Math.round(this.totalScore * 10) / 10,
      max_score: 100.0,
      percentage: Math.round(this.totalScore),
      status: this.totalScore >= 80.0 ? "Excellent" : this.totalScore >= 50.0 ? "Good" : "Needs Improvement",
      status_ar: this.totalScore >= 80.0 ? "ممتاز" : this.totalScore >= 50.0 ? "جيد" : "يحتاج تحسين",
      elements: this.details,
      missing_elements: this.missingElements,
      penalties_applied: this.appliedDeductions,
      academic_references: [
        "[Tech Resume Standards] Proof of Work: Projects must include repository links (GitHub/GitLab) or live URLs.",
        "[Content Guidelines] Projects must have adequate descriptions rather than just titles."
      ]
    };
  }
}

export class SummaryScorer {
  /**
   * Evaluates Professional Summary Quality (100 points max)
   */
  constructor(parsedJson) {
    this.data = parsedJson || {};
    this.summarySection = this.data.sections?.sections?.summary || {};
    this.summaryText = String(this.data.summary || this.data.entities?.summary || this.summarySection.content || '').trim();
    this.totalScore = 0.0;
    this.details = {};
    this.appliedDeductions = [];
    this.missingElements = [];
  }

  evaluate() {
    this.totalScore = 0.0;
    this.details = {};
    this.appliedDeductions = [];
    this.missingElements = [];

    // 1. Existence (40 max)
    if (!this.summaryText) {
      this.missingElements.push("Comprehensive Professional Summary");
      this.appliedDeductions.push({
        section: "Summary",
        reason: "Professional Summary is entirely missing.",
        penalty: -40.0,
        reference: "Standard CV Guidelines - Missing Core Section"
      });
      return {
        section_name: "Professional Summary Quality",
        section_name_ar: "الملخص المهني",
        score: 0.0,
        max_score: 100.0,
        percentage: 0,
        status: "Needs Improvement",
        status_ar: "يحتاج تحسين",
        elements: {},
        missing_elements: this.missingElements,
        penalties_applied: this.appliedDeductions
      };
    }

    this.totalScore += 40.0;
    this.details["Summary Existence"] = { score: 40.0, max: 40.0, status: "Found" };

    // 2. Length & Brevity (30 max) - 3-4 lines (30-85 words)
    const words = this.summaryText.split(/\s+/).filter(Boolean).length;
    let lengthScore = 0.0;
    if (words >= 30 && words <= 85) {
      lengthScore = 30.0;
    } else if (words > 85) {
      lengthScore = 15.0;
      this.appliedDeductions.push({
        section: "Summary",
        reason: `Summary is too long (${words} words). It should be a concise 3-4 lines.`,
        penalty: -15.0,
        reference: "CV Writing Standards (Brevity)"
      });
    } else {
      lengthScore = 15.0;
      this.appliedDeductions.push({
        section: "Summary",
        reason: `Summary is too short (${words} words). It should adequately highlight skills in 3-4 lines.`,
        penalty: -15.0,
        reference: "CV Writing Standards (Brevity)"
      });
    }
    this.totalScore += lengthScore;
    this.details["Length & Brevity (3-4 lines)"] = { score: lengthScore, max: 30.0, word_count: words };

    // 3. Tone & Quality (30 max) - First-person pronouns check
    let toneScore = 30.0;
    const firstPersonPronouns = [" i ", " me ", " my ", " mine ", " أنا ", " لي "];
    const paddedContent = ` ${this.summaryText.toLowerCase()} `;
    for (const p of firstPersonPronouns) {
      if (paddedContent.includes(p)) {
        toneScore -= 10.0;
        this.appliedDeductions.push({
          section: "Summary",
          reason: "Detected first-person pronouns (I, me, my, أنا). A professional summary should avoid them.",
          penalty: -10.0,
          reference: "Professional Resume Tone Guidelines"
        });
        break;
      }
    }
    this.totalScore += Math.max(0.0, toneScore);
    this.details["Content Quality & Tone"] = { score: Math.max(0.0, toneScore), max: 30.0 };

    this.totalScore = Math.max(0.0, Math.min(100.0, this.totalScore));

    return {
      section_name: "Professional Summary Quality",
      section_name_ar: "الملخص المهني",
      score: Math.round(this.totalScore * 10) / 10,
      max_score: 100.0,
      percentage: Math.round(this.totalScore),
      status: this.totalScore >= 85.0 ? "Excellent" : this.totalScore >= 60.0 ? "Good" : "Needs Improvement",
      status_ar: this.totalScore >= 85.0 ? "ممتاز" : this.totalScore >= 60.0 ? "جيد" : "يحتاج تحسين",
      elements: this.details,
      missing_elements: this.missingElements,
      penalties_applied: this.appliedDeductions,
      academic_references: [
        "[Standard CV Guidelines] The summary is a core section highlighting skills and achievements.",
        "[Brevity Standards] A summary must be concise, typically 3-4 lines (30-85 words).",
        "[Professional Tone] Resumes should be written without first-person pronouns (I, me, my)."
      ]
    };
  }
}

export class MasterScorer {
  /**
   * Master Scorer combining all individual section scorers using academic weights:
   * Contact: 5%
   * Section: 5%
   * Summary: 10%
   * Projects: 10%
   * Skills: 20%
   * Experience: 25%
   * Achievements: 25%
   */
  constructor(parsedJson) {
    this.parsedJson = parsedJson || {};
    this.weights = {
      contact: 0.05,
      section: 0.05,
      summary: 0.10,
      projects: 0.10,
      skills: 0.20,
      experience: 0.25,
      achievements: 0.25
    };
  }

  generateReport() {
    const contactRes = new ContactScorer(this.parsedJson).evaluate();
    const sectionRes = new SectionScorer(this.parsedJson).evaluate();
    const summaryRes = new SummaryScorer(this.parsedJson).evaluate();
    const projectsRes = new ProjectsScorer(this.parsedJson).evaluate();
    const skillsRes = new SkillsScorer(this.parsedJson).evaluate();
    const experienceRes = new ExperienceScorer(this.parsedJson).evaluate();
    const achievementsRes = new AchievementsScorer(this.parsedJson).evaluate();

    // Calculate normalized 100 scores
    const contactNorm = (contactRes.score / contactRes.max_score) * 100;
    const sectionNorm = (sectionRes.score / sectionRes.max_score) * 100;
    const summaryNorm = (summaryRes.score / summaryRes.max_score) * 100;
    const projectsNorm = (projectsRes.score / projectsRes.max_score) * 100;
    const skillsNorm = (skillsRes.score / skillsRes.max_score) * 100;
    const expNorm = (experienceRes.score / experienceRes.max_score) * 100;
    const achNorm = (achievementsRes.score / achievementsRes.max_score) * 100;

    const weightedScore = Math.round(
      (contactNorm * this.weights.contact) +
      (sectionNorm * this.weights.section) +
      (summaryNorm * this.weights.summary) +
      (projectsNorm * this.weights.projects) +
      (skillsNorm * this.weights.skills) +
      (expNorm * this.weights.experience) +
      (achNorm * this.weights.achievements)
    );

    const overallScore = Math.max(0, Math.min(100, weightedScore));

    const allPenalties = [
      ...contactRes.penalties_applied,
      ...sectionRes.penalties_applied,
      ...summaryRes.penalties_applied,
      ...projectsRes.penalties_applied,
      ...skillsRes.penalties_applied,
      ...experienceRes.penalties_applied,
      ...achievementsRes.penalties_applied
    ];

    const allMissingElements = [
      ...contactRes.missing_elements,
      ...sectionRes.missing_elements,
      ...summaryRes.missing_elements,
      ...projectsRes.missing_elements,
      ...skillsRes.missing_elements,
      ...experienceRes.missing_elements,
      ...achievementsRes.missing_elements
    ];

    let overallLabel = 'Fair';
    let overallLabelAr = 'متوسط';
    if (overallScore >= 85) {
      overallLabel = 'Excellent';
      overallLabelAr = 'ممتاز';
    } else if (overallScore >= 70) {
      overallLabel = 'Good';
      overallLabelAr = 'جيد';
    } else if (overallScore >= 50) {
      overallLabel = 'Fair';
      overallLabelAr = 'متوسط';
    } else {
      overallLabel = 'Needs Improvement';
      overallLabelAr = 'يحتاج تحسين';
    }

    return {
      overall_score: overallScore,
      max_score: 100,
      overall_status: overallLabel,
      overall_status_ar: overallLabelAr,
      score_breakdown: {
        contact: { ...contactRes, weight_percentage: '5%', normalized_100: Math.round(contactNorm * 10) / 10 },
        section: { ...sectionRes, weight_percentage: '5%', normalized_100: Math.round(sectionNorm * 10) / 10 },
        summary: { ...summaryRes, weight_percentage: '10%', normalized_100: Math.round(summaryNorm * 10) / 10 },
        projects: { ...projectsRes, weight_percentage: '10%', normalized_100: Math.round(projectsNorm * 10) / 10 },
        skills: { ...skillsRes, weight_percentage: '20%', normalized_100: Math.round(skillsNorm * 10) / 10 },
        experience: { ...experienceRes, weight_percentage: '25%', normalized_100: Math.round(expNorm * 10) / 10 },
        achievements: { ...achievementsRes, weight_percentage: '25%', normalized_100: Math.round(achNorm * 10) / 10 }
      },
      all_penalties: allPenalties,
      all_missing_elements: allMissingElements
    };
  }
}
