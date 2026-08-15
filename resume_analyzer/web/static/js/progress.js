"use strict";

document.addEventListener("DOMContentLoaded", () => {
  const view = document.getElementById("progress-view");
  if (!view) return;

  const analysisId = view.dataset.analysisId;
  const alertBox = document.getElementById("progress-alert");

  // ✅ قائمة جميع المراحل بالترتيب الصحيح
  const ALL_STAGES = [
    "uploading", "validating_document", "extracting_text",
    "detecting_sections", "extracting_entities",
    "suggesting_target_role", "generating_recommendations",
    "calculating_ats", "matching_job", "generating_rewrites",
    "validating_final_report", "completed"
  ];

  // 🔄 خريطة لتطابق أسماء المراحل من الـ API
  const STAGE_MAP = {
    "running_pipeline": "extracting_text",  // المرحلة الفعلية بعد التحقق
    "upload": "uploading",
    "uploading_document": "uploading",
    "validate": "validating_document",
    "validating": "validating_document",
    "extract_text": "extracting_text",
    "text_extraction": "extracting_text",
    "detect_sections": "detecting_sections",
    "section_detection": "detecting_sections",
    "extract_entities": "extracting_entities",
    "entity_extraction": "extracting_entities",
    "suggest_role": "suggesting_target_role",
    "target_role": "suggesting_target_role",
    "generate_recommendations": "generating_recommendations",
    "calculate_ats": "calculating_ats",
    "ats_score": "calculating_ats",
    "match_job": "matching_job",
    "job_matching": "matching_job",
    "generate_rewrites": "generating_rewrites",
    "rewrites": "generating_rewrites",
    "validate_final": "validating_final_report",
    "final_report": "validating_final_report",
    "complete": "completed",
    "done": "completed"
  };

  let isPolling = false;
  let isAnalysisFinished = false;
  let pipelineStarted = false;
  let lastCompletedCount = 0;

  // ════════════════════════════════════════════════════════════════
  // 1️⃣ دوال تحديث الواجهة
  // ════════════════════════════════════════════════════════════════

  const markStageActive = (stageKey) => {
    const el = document.querySelector(`[data-stage="${stageKey}"]`);
    if (!el) return;
    el.classList.remove("is-complete");
    el.classList.add("is-active");
    const statusEl = el.querySelector(".step-status");
    if (statusEl) statusEl.textContent = "IN PROGRESS";
  };

  const markStageComplete = (stageKey) => {
    const el = document.querySelector(`[data-stage="${stageKey}"]`);
    if (!el) return;
    el.classList.remove("is-active");
    el.classList.add("is-complete");
    const statusEl = el.querySelector(".step-status");
    if (statusEl) statusEl.textContent = "COMPLETED";
  };

  // ════════════════════════════════════════════════════════════════
  // 2️⃣ تحويل اسم المرحلة من الـ API إلى اسمنا
  // ════════════════════════════════════════════════════════════════

  const normalizeStageName = (stageName) => {
    if (!stageName) return null;
    const normalized = stageName.toLowerCase().trim();

    // التحقق المباشر من الخريطة
    if (STAGE_MAP[normalized]) {
      return STAGE_MAP[normalized];
    }

    // التحقق من التطابق المباشر
    if (ALL_STAGES.includes(normalized)) {
      return normalized;
    }

    return null;
  };

  // ════════════════════════════════════════════════════════════════
  // 3️⃣ تحديث التقدم بناءً على المراحل المكتملة
  // ════════════════════════════════════════════════════════════════

  const updateProgressFromCompletedStages = (completedStages) => {
    if (!completedStages || !Array.isArray(completedStages)) return;
    if (isAnalysisFinished) return;

    let highestIndex = -1;

    // البحث عن أعلى مرحلة مكتملة
    for (const stage of completedStages) {
      const normalized = normalizeStageName(stage);
      if (normalized) {
        const index = ALL_STAGES.indexOf(normalized);
        if (index > highestIndex) {
          highestIndex = index;
        }
      }
    }

    // إذا تم العثور على مراحل مكتملة
    if (highestIndex >= 0) {
      console.log(`✅ Completed stages up to: ${ALL_STAGES[highestIndex]} (index: ${highestIndex})`);

      // تعليم جميع المراحل حتى أعلى مرحلة مكتملة
      for (let i = 0; i <= highestIndex; i++) {
        if (i < ALL_STAGES.length - 1) {
          markStageComplete(ALL_STAGES[i]);
        }
      }

      // المرحلة التالية تصبح نشطة (إذا لم نصل للنهاية)
      const nextIndex = highestIndex + 1;
      if (nextIndex < ALL_STAGES.length - 1) {
        markStageActive(ALL_STAGES[nextIndex]);
        console.log(`🔄 Next stage: ${ALL_STAGES[nextIndex]}`);
      } else if (nextIndex >= ALL_STAGES.length - 1) {
        // إذا وصلنا لآخر مرحلة
        markStageActive("completed");
      }

      return true;
    }

    return false;
  };

  // ════════════════════════════════════════════════════════════════
  // 4️⃣ تشغيل المسار البصري (محاكاة التقدم)
  // ════════════════════════════════════════════════════════════════

  const startVisualPipeline = () => {
    if (pipelineStarted) return;
    pipelineStarted = true;

    // نبدأ من أول مرحلة
    const simulationStages = ALL_STAGES.slice(0, -1);
    let simIndex = 0;

    // تفعيل أول مرحلة
    markStageActive(simulationStages[0]);

    const interval = setInterval(() => {
      if (isAnalysisFinished) {
        clearInterval(interval);
        return;
      }

      // تعليم المرحلة الحالية كمكتملة
      markStageComplete(simulationStages[simIndex]);
      simIndex++;

      // إذا انتهت جميع المراحل
      if (simIndex >= simulationStages.length) {
        clearInterval(interval);
        markStageActive("completed");
        return;
      }

      // تفعيل المرحلة التالية
      markStageActive(simulationStages[simIndex]);

    }, 3000);
  };

  // ════════════════════════════════════════════════════════════════
  // 5️⃣ معالجة استجابة الـ API
  // ════════════════════════════════════════════════════════════════

  const processApiResponse = (payload) => {
    console.log("📦 Processing API response:", payload);

    // 1. محاولة استخدام completed_stages (الأهم)
    if (payload.completed_stages && Array.isArray(payload.completed_stages)) {
      const updated = updateProgressFromCompletedStages(payload.completed_stages);
      if (updated) {
        // التحقق من عدد المراحل المكتملة
        const count = payload.completed_stages.length;
        if (count !== lastCompletedCount) {
          lastCompletedCount = count;
          console.log(`📊 Completed stages: ${count}/${ALL_STAGES.length - 1}`);
        }
        return true;
      }
    }

    // 2. محاولة استخراج المرحلة من stage
    if (payload.stage) {
      const normalized = normalizeStageName(payload.stage);
      if (normalized) {
        console.log(`🎯 Stage mapped: ${payload.stage} → ${normalized}`);
        const index = ALL_STAGES.indexOf(normalized);
        if (index > 0) {
          // تعليم كل المراحل حتى هذه المرحلة
          for (let i = 0; i < index; i++) {
            if (i < ALL_STAGES.length - 1) {
              markStageComplete(ALL_STAGES[i]);
            }
          }
          if (index < ALL_STAGES.length - 1) {
            markStageActive(normalized);
          }
          return true;
        }
      }
    }

    // 3. إذا كانت الحالة "running" ولم تبدأ المحاكاة
    if (payload.status === "running" && !pipelineStarted) {
      console.log("🔄 Status is 'running', starting visual pipeline");
      startVisualPipeline();
      return true;
    }

    return false;
  };

  // ════════════════════════════════════════════════════════════════
  // 6️⃣ Polling Loop
  // ════════════════════════════════════════════════════════════════

  const poll = async () => {
    if (isPolling) return;
    isPolling = true;

    try {
      const response = await fetch(`/api/analyses/${analysisId}`, {
        headers: { "Accept": "application/json" }
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const payload = await response.json();
      console.log("📥 Polling response:", payload);

      // ✅ التحقق من حالة الانتهاء
      if (payload.status === "completed" || payload.status === "done" ||
          payload.result_available === true) {
        isAnalysisFinished = true;

        // تعليم جميع المراحل كمكتملة
        ALL_STAGES.forEach(stage => {
          if (stage !== "completed") markStageComplete(stage);
        });
        markStageActive("completed");

        setTimeout(() => {
          window.location.reload();
        }, 2500);
        return;
      }

      // ❌ التحقق من حالة الفشل
      if (payload.status === "failed" || payload.error) {
        isAnalysisFinished = true;
        const errorMsg = payload.error?.message || payload.message || "Analysis failed.";
        alertBox.textContent = errorMsg;
        alertBox.classList.remove("d-none");
        return;
      }

      // ⚙️ معالجة الاستجابة
      const processed = processApiResponse(payload);

      if (!processed && !pipelineStarted) {
        console.log("🔄 Starting visual pipeline as fallback");
        startVisualPipeline();
      }

    } catch (error) {
      console.error("❌ Polling error:", error);
      if (!pipelineStarted) {
        startVisualPipeline();
      }
    } finally {
      isPolling = false;
      if (!isAnalysisFinished) {
        setTimeout(poll, 2000);
      }
    }
  };

  // ════════════════════════════════════════════════════════════════
  // 7️⃣ بدء التشغيل
  // ════════════════════════════════════════════════════════════════

  console.log("🚀 Starting progress tracking...");
  console.log("📋 Analysis ID:", analysisId);
  console.log("📋 API Response Structure:");
  console.log("   - status: running | completed | failed");
  console.log("   - stage: running_pipeline | ...");
  console.log("   - completed_stages: [list of completed stages]");
  console.log("   - result_available: true | false");

  // بدء المحاكاة
  startVisualPipeline();

  // بدء الـ Polling
  poll();
});
