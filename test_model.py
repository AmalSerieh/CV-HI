import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

model_name = "Qwen/Qwen2.5-0.5B-Instruct"

tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype="auto",
    device_map="auto"
)

# --- 1. إدخال بيانات السيرة الذاتية والوظيفة المستهدفة ---
cv_text = """
الاسم: أحمد علي
الخبرات: عملت لمؤخراً كـ Python Developer لمدة سنة، قمت ببناء APIs باستخدام Flask، ولدي خبرة بسيطة في قواعد البيانات MySQL.
التعليم: بكالوريوس علوم حاسوب.
"""

job_description = """
مطلوب Backend Developer خبرة في Python و Django/Flask، معرفة ممتازة بـ SQL، ويفضل من لديه خبرة في تحسين أداء استعلامات قواعد البيانات.
"""

# --- 2. تحديد دور النموذج (System Prompt) مع التعليمات ---
messages = [
    {
        "role": "system",
        "content": (
            "أنت خبير محترف في مراجعة وتحسين السير الذاتية (CV Optimizer). "
            "مهامك هي: مقارنة السيرة الذاتية بالمتطلبات الوظيفية، تحديد النواقص، "
            "واقتراح تحسينات ملموسة لإبراز مهارات المتقدم."
        )
    },
    {
        "role": "user",
        "content": f"""
بيانات السيرة الذاتية:
{cv_text}

الوصف الوظيفي المستهدف:
{job_description}

بناءً على ذلك، يرجى تقديم:
1. المهارات المفقودة أو التي تحتاج إبرازها أكثر.
2. اقتراحات لتحسين صياغة قسم الخبرات لتتناسب مع الوظيفة.
"""
    }
]

# --- 3. المعالجة والتوليد ---
text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
model_inputs = tokenizer([text], return_tensors="pt").to(model.device)

# تم زيادة max_new_tokens لإعطاء مساحة لإجابة مفصلة
generated_ids = model.generate(
    **model_inputs,
    max_new_tokens=700,
    temperature=0.7,
    do_sample=True
)

generated_ids = [
    output_ids[len(input_ids) :]
    for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
]

response = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]

print("\n=== توصيات تحسين السيرة الذاتية ===\n")
print(response)