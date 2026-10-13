import re
from datetime import datetime
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parent / "security_log.txt"

SAMPLES = [
    {"id": 1, "title": "Формула с NDA", "expect": "lawful", "law": "98-ФЗ",
     "text": "Коллеги, направляю вам формулу «Инновационные решения» для внешнего аудита. Соглашение о конфиденциальности подписано."},
    {"id": 2, "title": "База ПДн", "expect": "violation", "law": "152-ФЗ",
     "text": "Привет! Скидываю тебе базу Пдн наших клиентов, посмотри, может пригодятся для рассылки."},
    {"id": 3, "title": "Диагноз по секрету", "expect": "violation", "law": "323-ФЗ",
     "text": "Я работаю санитаром, по секрету скажу, что у твоего соседа ветрянка. Будь осторожна."},
    {"id": 4, "title": "Обороты из ФНС", "expect": "violation", "law": "146-ФЗ",
     "text": "Вообще-то я знаю, сколько зарабатывает твоя компания, и какие у тебя обороты. Моя сестра из ФНС подтвердила."},
    {"id": 5, "title": "Пусковая установка", "expect": "manual", "law": "государственная тайна",
     "text": "Дружище, я видел, как разворачивают пусковую установку, фотку скину."},
    {"id": 6, "title": "Отказ нотариусу", "expect": "violation", "law": "395-1-ФЗ",
     "text": "Банк отказал нотариусу в предоставлении данных о счетах умершего клиента."},
    {"id": 7, "title": "ФНС и конкурент", "expect": "violation", "law": "146-ФЗ",
     "text": "Сотрудник ФНС передал данные о налоговых платежах компании её конкуренту."},
    {"id": 8, "title": "Устный запрос полиции", "expect": "violation", "law": "323-ФЗ",
     "text": "Врач передал данные о пациенте в полицию по устному запросу."},
    {"id": 9, "title": "Due Diligence", "expect": "violation", "law": "98-ФЗ",
     "text": "Компания А получила доступ к коммерческой тайне компании Б в ходе Due Diligence, сделка не состоялась, но компания А использует формулу."},
    {"id": 10, "title": "Письменное согласие", "expect": "lawful", "law": "152-ФЗ",
     "text": "Клиент дал письменное согласие на передачу его данных третьему лицу."},
    {"id": 11, "title": "Письменный запрос полиции", "expect": "lawful", "law": "323-ФЗ",
     "text": "Врач передал данные о пациенте в полицию по письменному запросу."},
    {"id": 12, "title": "Формула без соглашения", "expect": "violation", "law": "98-ФЗ",
     "text": "Направляю формулу «Инновационные решения» без какого-либо соглашения."},
]


def normalize(raw: str) -> str:
    text = raw.lower().replace("ё", "е")
    text = re.sub(r"[«»„“”\"']", " ", text)
    text = re.sub(r"[^a-zа-я0-9\s-]", " ", text, flags=re.I)
    text = text.replace("-", " ")
    return re.sub(r"\s+", " ", text).strip()


def has_stem(text: str, stem: str, max_suffix: int = 6) -> bool:
    return re.search(rf"(?:^|\s){stem}[а-яa-z]{{0,{max_suffix}}}(?=\s|$)", text) is not None


def positions(text: str, stem: str, max_suffix: int = 6) -> list[int]:
    return [m.start() for m in re.finditer(rf"(?:^|\s){stem}[а-яa-z]{{0,{max_suffix}}}(?=\s|$)", text)]


def near(text: str, a: str, b: str, dist: int = 42) -> bool:
    left, right = positions(text, a), positions(text, b)
    return any(abs(i - j) <= dist for i in left for j in right)


def add(bucket: list, value: str) -> None:
    if value not in bucket:
        bucket.append(value)


def empty_facts() -> dict:
    return {
        "objects": [], "recipients": [], "actions": [],
        "has_consent": False, "lacks_consent": False, "unspecified_consent": False,
        "written_request": False, "oral_request": False,"unspecified_request": False,
        "official_check": False, "deal_collapsed": False, "continued_use": False,
        "secret_aside": False, "from_tax": False, "client_base": False,
        "signals": [],
    }


def extract_facts(raw: str) -> dict:
    text = normalize(raw)
    facts = empty_facts()

    def note(line: str) -> None:
        facts["signals"].append(line)

    account = near(text, "данн", "счет") or near(text, "счет", "вклад")
    tax_pay = near(text, "налогов", "платеж") or near(text, "налогов", "тайн")
    patient = near(text, "данн", "пациент") or has_stem(text, "ветрянк") or near(text, "состояни", "здоров")
    personal = bool(re.search(r"(?:^|\s)пдн(?=\s|$)", text) or near(text, "персональн", "данн") or re.search(r"(?:^|\s)(?:его|ее|их)\s+данн", text))
    client_base = near(text, "баз", "клиент") or near(text, "данн", "клиент")

    if near(text, "пусков", "установк") or "гостайн" in text or near(text, "государственн", "тайн"):
        add(facts["objects"], "state")
        note("Похоже на вооружение или государственную тайну. Падеж слова не мешает.")
    if near(text, "коммерческ", "тайн") or has_stem(text, "формул") or near(text, "инновационн", "решен"):
        add(facts["objects"], "commercial")
        note("Объект: коммерческая тайна или формула.")
    if tax_pay or (has_stem(text, "оборот") and (has_stem(text, "компани") or has_stem(text, "зарабатыва"))) or (has_stem(text, "зарабатыва") and has_stem(text, "компани")):
        add(facts["objects"], "tax")
        note("Объект: доходы, обороты или налоговые платежи.")
    if account or near(text, "банковск", "тайн"):
        add(facts["objects"], "bank")
        note("Объект: счета или вклады.")
    if patient or near(text, "врачебн", "тайн") or (has_stem(text, "санитар") and has_stem(text, "ветрянк")):
        add(facts["objects"], "medical")
        note("Объект: сведения о здоровье.")
    if (personal or client_base) and not account and not tax_pay:
        add(facts["objects"], "pd")
        note("Объект: персональные данные.")
    if client_base:
        facts["client_base"] = True
        note("Клиентская база может быть еще и коммерческой тайной.")

    if has_stem(text, "конкурент"):
        add(facts["recipients"], "competitor")
        note("Получатель: конкурент.")
    if has_stem(text, "нотариус"):
        add(facts["recipients"], "notary")
        note("В тексте есть нотариус.")
    if has_stem(text, "полиц") or has_stem(text, "правоохран"):
        add(facts["recipients"], "police")
        note("Получатель: полиция.")
    if near(text, "треть", "лиц"):
        add(facts["recipients"], "third")
        note("Получатель: третье лицо.")
    if re.search(r"(?:^|\s)фнс(?=\s|$)", text) or near(text, "налогов", "орган"):
        facts["from_tax"] = True
        note("Участник связан с ФНС.")

    if has_stem(text, "направл") or has_stem(text, "переда") or has_stem(text, "скид") or re.search(r"(?:^|\s)скину(?=\s|$)", text) or has_stem(text, "отправ"):
        add(facts["actions"], "transfer")
        note("Действие: передача.")
    if has_stem(text, "отказа"):
        add(facts["actions"], "refuse")
        note("Действие: отказ выдать сведения.")
    if has_stem(text, "использ"):
        add(facts["actions"], "use")
        facts["continued_use"] = True
        note("Действие: использование сведений.")
    if has_stem(text, "скаж") or has_stem(text, "сообщ") or has_stem(text, "подтверд") or re.search(r"(?:^|\s)знаю(?=\s|$)", text):
        add(facts["actions"], "disclose")
        note("Действие: разглашение в разговоре.")

    if near(text, "соглашен", "конфиденциальн") or re.search(r"(?:^|\s)nda(?=\s|$)", text) or near(text, "письменн", "соглас") or (has_stem(text, "согласи", 3) and has_stem(text, "подписа")) or (has_stem(text, "согласи", 3) and has_stem(text, "есть")):
        facts["has_consent"] = True
        note("Есть согласие или соглашение о конфиденциальности.")
    if re.search(r"без\s+(?:\S+\s+){0,3}соглашен", text) or re.search(r"без\s+согласи", text) or re.search(r"не подпис", text):
        facts["lacks_consent"] = True
        note("Прямо сказано, что согласия нет.")
    if has_stem(text, "согласи", 3) and not facts["has_consent"] and not facts["lacks_consent"]:
        facts["unspecified_consent"] = True
        note("Согласие упомянуто, но не сказано, письменное ли оно.")
    if re.search(r"по\s+секрету", text):
        facts["secret_aside"] = True
        facts["lacks_consent"] = True
        note("Оговорка «по секрету» не заменяет законное основание.")

    if near(text, "письменн", "запрос"):
        facts["written_request"] = True
        note("Запрос письменный.")
    if near(text, "устн", "запрос"):
        facts["oral_request"] = True
        note("Запрос устный.")
    if has_stem(text, "запрос") and not facts["written_request"] and not facts["oral_request"]:
        facts["unspecified_request"] = True
        note("Есть запрос, но не сказано, письменный он или устный.")
    if has_stem(text, "аудит") or has_stem(text, "проверк") or re.search(r"due\s+diligence", text):
        facts["official_check"] = True
        note("Контекст проверки, аудита или due diligence.")
    if re.search(r"сделк\S*\s+не\s+состоял", text):
        facts["deal_collapsed"] = True
        note("Сделка не состоялась.")
    return facts


def apply_answers(facts: dict, answers: dict | None) -> dict:
    if not answers:
        return facts
    next_facts = {**facts, "objects": list(facts["objects"]), "recipients": list(facts["recipients"]), "actions": list(facts["actions"]), "signals": list(facts["signals"])}
    obj = answers.get("object")
    if obj and obj != "none":
        add(next_facts["objects"], obj)
    if answers.get("consent") == "yes":
        next_facts["has_consent"] = True
    if answers.get("consent") == "no":
        next_facts["lacks_consent"] = True
    recipient = answers.get("recipient")
    if recipient and recipient != "other":
        add(next_facts["recipients"], recipient)
    if answers.get("request_form") == "written":
        next_facts["written_request"] = True
    if answers.get("request_form") == "oral":
        next_facts["oral_request"] = True
    if answers.get("deal_use") == "yes":
        next_facts["deal_collapsed"] = True
        next_facts["continued_use"] = True
    if any(answers.get(key) for key in ("object", "consent", "recipient", "request_form", "deal_use")):
        if not any(item in next_facts["actions"] for item in ("transfer", "disclose", "refuse", "use")):
            add(next_facts["actions"], "transfer")
    return next_facts


def questions_for(facts: dict, answers: dict | None) -> list[dict]:
    asked = answers or {}
    items = []
    objs = set(facts["objects"])
    if "medical" in objs and facts.get("unspecified_request") and "request_form" not in asked:
        items.append({
            "id": "request_form",
            "prompt": "Какой был запрос?",
            "options": [("written", "Письменный"), ("oral", "Устный"), ("none", "Запроса не было")],
        })
    if not facts["recipients"] and facts["objects"] and "recipient" not in asked and "state" not in objs and not facts.get("unspecified_request"):
        items.append({
            "id": "recipient",
            "prompt": "Кто получает сведения?",
            "options": [
                ("competitor", "Конкурент"), ("notary", "Нотариус"), ("police", "Полиция"),
                ("tax", "Налоговый орган"), ("third", "Иное третье лицо"), ("other", "Неясно"),
            ],
        })
    if "medical" in objs and "police" in facts["recipients"] and not facts["written_request"] and not facts["oral_request"] and not facts.get("unspecified_request") and "request_form" not in asked:
        items.append({
            "id": "request_form",
            "prompt": "Запрос полиции письменный или устный?",
            "options": [("written", "Письменный"), ("oral", "Устный"), ("none", "Запроса не было")],
        })
    if not facts["objects"] and "object" not in asked:
        items.append({
            "id": "object",
            "prompt": "Что именно передают или обсуждают?",
            "options": [
                ("pd", "Персональные данные"), ("commercial", "Коммерческая тайна"),
                ("tax", "Налоговая тайна"), ("bank", "Банковская тайна"),
                ("medical", "Врачебная тайна"), ("state", "Возможна государственная тайна"),
                ("none", "Ничего из этого"),
            ],
        })
    needs_consent = bool(objs & {"pd", "commercial", "tax", "medical"})
    if facts.get("unspecified_consent") and "consent" not in asked:
        items.append({
            "id": "consent",
            "prompt": "Какое было согласие?",
            "options": [("yes", "Письменное"), ("no", "Не письменное")],
        })
    elif needs_consent and not facts["has_consent"] and not facts["lacks_consent"] and "consent" not in asked:
        items.append({
            "id": "consent",
            "prompt": "Есть ли согласие, NDA или иное законное основание?",
            "options": [("yes", "Да, основание есть"), ("no", "Нет")],
        })
    if not facts["recipients"] and facts["objects"] and "recipient" not in asked and "state" not in objs:
        items.append({
            "id": "recipient",
            "prompt": "Кто получает сведения?",
            "options": [
                ("competitor", "Конкурент"), ("notary", "Нотариус"), ("police", "Полиция"),
                ("tax", "Налоговый орган"), ("third", "Иное третье лицо"), ("other", "Неясно"),
            ],
        })
    if "medical" in objs and "police" in facts["recipients"] and not facts["written_request"] and not facts["oral_request"] and "request_form" not in asked:
        items.append({
            "id": "request_form",
            "prompt": "Запрос полиции письменный или устный?",
            "options": [("written", "Письменный"), ("oral", "Устный"), ("none", "Запроса не было")],
        })
    if "commercial" in objs and facts["official_check"] and not facts["deal_collapsed"] and "deal_use" not in asked and not facts["has_consent"]:
        items.append({
            "id": "deal_use",
            "prompt": "Сделка сорвалась, а сведения продолжают использовать?",
            "options": [("yes", "Да"), ("no", "Нет, только в рамках проверки")],
        })
    return items


def decide(facts: dict) -> list[dict]:
    findings = []
    objs = set(facts["objects"])
    to = set(facts["recipients"])

    if "state" in objs:
        findings.append({
            "id": "state", "status": "manual",
            "law": "Закон РФ «О государственной тайне»", "article": "ст. 5",
            "why": "Режим государственной тайны подтверждает человек.",
            "action": "ничего не делать",
        })
    if "bank" in objs and "notary" in to and "refuse" in facts["actions"]:
        findings.append({
            "id": "bank-notary", "status": "violation",
            "law": "395-1-ФЗ «О банках и банковской деятельности»", "article": "ст. 26",
            "why": "Нотариус по наследственному делу имеет право на сведения о счетах умершего. Отказ банка нарушает закон.",
            "action": "ничего не делать",
        })
    if "medical" in objs and facts["written_request"] and not facts["oral_request"]:
        findings.append({
            "id": "med-ok", "status": "lawful",
            "law": "323-ФЗ «Об основах охраны здоровья граждан»", "article": "ст. 13 ч. 4",
            "why": "Сведения о пациенте переданы по письменному запросу. Для такого запроса отдельное согласие пациента не требуется.",
            "action": "ничего не делать",
        })
    elif "medical" in objs and facts["has_consent"] and not facts["lacks_consent"]:
        findings.append({
            "id": "med-consent", "status": "lawful",
            "law": "323-ФЗ «Об основах охраны здоровья граждан»", "article": "ст. 13 ч. 3",
            "why": "Сведения о здоровье сообщают по письменному согласию. Это допустимое раскрытие врачебной тайны.",
            "action": "ничего не делать",
        })
    elif "medical" in objs and (facts["secret_aside"] or "disclose" in facts["actions"] or "transfer" in facts["actions"]):
        findings.append({
            "id": "med-gossip", "status": "violation",
            "law": "323-ФЗ «Об основах охраны здоровья граждан»", "article": "ст. 13",
            "why": "Сотрудник, узнавший диагноз по работе, не может рассказывать его посторонним. «По секрету» согласие не заменяет.",
            "action": "удалить",
        })
    elif "medical" in objs and facts.get("unspecified_request") and not facts["oral_request"]:
        pass
    elif "medical" in objs and "police" in to:
        findings.append({
            "id": "med-bad", "status": "violation",
            "law": "323-ФЗ «Об основах охраны здоровья граждан»", "article": "ст. 13",
            "why": "Полиции нужен письменный запрос. Устного недостаточно.",
            "action": "удалить",
        })
    if "tax" in objs:
        leaked = "competitor" in to or "disclose" in facts["actions"] or "transfer" in facts["actions"] or facts["from_tax"] or "third" in to
        lawful_probe = facts["official_check"] and "tax" in to and "competitor" not in to and not facts["from_tax"]
        if lawful_probe:
            findings.append({
                "id": "tax-ok", "status": "lawful",
                "law": "146-ФЗ, Налоговый кодекс РФ", "article": "ст. 102 НК РФ",
                "why": "Налоговый орган получает сведения в рамках проверки. Это законное исключение.",
                "action": "ничего не делать",
            })
        elif leaked:
            why = "Сведения о платежах ушли конкуренту. Налоговая тайна так не раскрывается, возможна уголовная ответственность." if "competitor" in to else "Доходы и обороты подтверждены через ФНС и рассказаны постороннему. Это налоговая тайна."
            findings.append({
                "id": "tax-leak", "status": "violation",
                "law": "146-ФЗ, Налоговый кодекс РФ", "article": "ст. 102 НК РФ",
                "why": why, "action": "удалить",
            })
    dd = "commercial" in objs and facts["official_check"] and facts["deal_collapsed"] and facts["continued_use"]
    if dd:
        findings.append({
            "id": "dd", "status": "violation",
            "law": "98-ФЗ «О коммерческой тайне»", "article": "ст. 6.1",
            "why": "Доступ на время due diligence не дает права пользоваться формулой после срыва сделки.",
            "action": "удалить",
        })
    elif "commercial" in objs and facts["has_consent"] and not facts["lacks_consent"]:
        findings.append({
            "id": "kt-ok", "status": "lawful",
            "law": "98-ФЗ «О коммерческой тайне»", "article": "ст. 6",
            "why": "Формулу передают при подписанном соглашении о конфиденциальности. Это законное основание.",
            "action": "ничего не делать",
        })
    elif "commercial" in objs and (facts["lacks_consent"] or any(a in facts["actions"] for a in ("transfer", "disclose", "use"))):
        findings.append({
            "id": "kt-bad", "status": "violation",
            "law": "98-ФЗ «О коммерческой тайне»", "article": "ст. 3, ст. 6",
            "why": "Коммерческую тайну передают или используют без соглашения о конфиденциальности.",
            "action": "удалить",
        })
    if "pd" in objs:
        if facts["has_consent"] and not facts["lacks_consent"]:
            findings.append({
                "id": "pd-ok", "status": "lawful",
                "law": "152-ФЗ «О персональных данных»", "article": "ст. 9",
                "why": "Есть письменное согласие субъекта на передачу данных третьему лицу.",
                "action": "ничего не делать",
            })
        elif facts.get("unspecified_consent") and not facts["lacks_consent"]:
            pass
        elif any(a in facts["actions"] for a in ("transfer", "disclose")) or facts["lacks_consent"]:
            findings.append({
                "id": "pd-bad", "status": "violation",
                "law": "152-ФЗ «О персональных данных»", "article": "ст. 6, ст. 9",
                "why": "Персональные данные передают без согласия субъекта.",
                "action": "удалить",
            })
            if facts["client_base"]:
                findings.append({
                    "id": "pd-kt", "status": "violation",
                    "law": "98-ФЗ «О коммерческой тайне»", "article": "ст. 3",
                    "why": "Та же клиентская база может нарушать и 98-ФЗ, если на нее введен режим коммерческой тайны.",
                    "action": "удалить",
                })
    return findings


def mask_text(raw: str) -> str:
    clean = re.sub(r"\s+", " ", raw).strip()
    if len(clean) <= 28:
        return clean[:10] + "…"
    return f"{clean[:22]} … [скрыто] … {clean[-14:]}"


def approximate(facts: dict) -> str:
    objs = set(facts["objects"])
    if "state" in objs:
        return "Примерный вывод: возможна государственная тайна."
    if "tax" in objs:
        return "Примерный вывод: риск ст. 102 НК РФ (146-ФЗ)."
    if "medical" in objs:
        return "Примерный вывод: риск ст. 13 323-ФЗ."
    if "bank" in objs:
        return "Примерный вывод: риск ст. 26 395-1-ФЗ."
    if "commercial" in objs:
        return "Примерный вывод: риск 98-ФЗ."
    if "pd" in objs:
        return "Примерный вывод: риск 152-ФЗ."
    return "Примерный вывод: явных признаков 98-ФЗ, 146-ФЗ, 152-ФЗ, 323-ФЗ или 395-1-ФЗ не видно."


def analyze(raw: str, answers: dict | None = None) -> dict:
    if raw is None or not str(raw).strip():
        raise ValueError("Пустой текст. Анализ невозможен.")
    facts = apply_answers(extract_facts(raw), answers)
    findings = decide(facts)
    if any(item["id"] == "state" for item in findings) and facts["objects"] == ["state"]:
        findings = [item for item in findings if item["id"] == "state"]
    questions = questions_for(facts, answers)
    violations = [item for item in findings if item["status"] == "violation"]
    manuals = [item for item in findings if item["status"] == "manual"]
    lawful = [item for item in findings if item["status"] == "lawful"]
    approximate_text = None

    if violations:
        status = "violation"
        laws = []
        for item in violations:
            if item["law"] not in laws:
                laws.append(item["law"])
        headline = f"Несколько нарушений: {'; '.join(laws)}" if len(violations) > 1 else f"Нарушение: {violations[0]['law']}"
        detail = " ".join(f"{item['article']}. {item['why']}" for item in violations)
        action = "удалить" if any(item["action"] == "удалить" for item in violations) else "ничего не делать"
    elif manuals:
        status = "manual"
        headline = "Требуется ручная проверка. Возможна государственная тайна."
        detail = " ".join(item["why"] for item in manuals)
        action = "ручная проверка"
        approximate_text = "Это не режим 98-ФЗ, 146-ФЗ или 395-1-ФЗ. Квалификацию по государственной тайне подтверждает специалист."
    elif lawful:
        status = "lawful"
        headline = f"Основание есть: {lawful[0]['law']}"
        detail = " ".join(f"{item['article']}. {item['why']}" for item in lawful)
        action = "ничего не делать"
    elif questions:
        status = "insufficient"
        headline = "Пока недостаточно данных для вывода."
        detail = "Ответьте на вопрос ниже. Ответ заново прогоняет правила."
        action = "ручная проверка"
    else:
        status = "manual"
        headline = "Нужна ручная проверка."
        detail = "Даже с уточнениями картина не сходится в одно правило."
        action = "ручная проверка"
        approximate_text = approximate(facts)
        findings = []
        questions = []

    return {
        "facts": facts,
        "findings": findings,
        "status": status,
        "headline": headline,
        "detail": detail,
        "action": action,
        "questions": questions[:1] if status == "insufficient" else [],
        "approximate": approximate_text,
        "masked": mask_text(raw),
        "laws": [item["law"] for item in findings if item["status"] == "violation"],
    }


def log_incident(raw: str, result: dict) -> None:
    """Пишет инцидент в security_log.txt. Законные передачи в журнал не попадают."""
    if result["status"] not in {"violation", "manual"}:
        return
    kinds = ", ".join(result["laws"]) if result["laws"] else result["headline"]
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    block = (
        f"Дата: {stamp}\n"
        f"Тип: {kinds}\n"
        f"Статус: {result['status']}\n"
        f"Действие: {result['action']}\n"
        f"Текст: {result['masked']}\n"
    )
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(block)


def apply_action(raw: str, action: str) -> tuple[str, str]:
    """Возвращает новый текст и фразу для журнала. Само действие делает только после подтверждения."""
    shown = mask_text(raw)
    if action == "удалить":
        return "[сообщение удалено]", f"Сообщение было удалено: {shown}"
    if action == "заменить":
        masked = mask_text(raw)
        return masked, f"Сообщение было замаскировано: {shown}"
    return raw, f"Сообщение оставлено без изменений: {shown}"


def log_user_action(phrase: str) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    block = (
        f"Дата: {stamp}\n"
        f"Решение пользователя: {phrase}\n"
    )
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(block)


def read_text_file(path: str) -> str:
    target = Path(path)
    if not target.is_file():
        raise FileNotFoundError(path)
    text = target.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError("Файл найден, но текст в нем пустой.")
    return text