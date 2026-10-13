from pathlib import Path

from flask import Flask, render_template, request

from analyzer import SAMPLES, analyze, apply_action, log_incident, log_user_action, read_text_file

app = Flask(__name__)


def answers_from_form() -> dict:
    found = {}
    for key in ("object", "consent", "recipient", "request_form", "deal_use"):
        value = request.form.get(key, "").strip()
        if value:
            found[key] = value
    return found


@app.route("/", methods=["GET", "POST"])
def index():
    error = None
    result = None
    applied = None
    text = request.form.get("text", "") if request.method == "POST" else ""
    source = ""
    path_value = request.form.get("path", "").strip() if request.method == "POST" else ""
    if request.method == "POST" and request.form.get("confirm_action"):
        try:
            action = request.form.get("confirm_action", "").strip()
            if action not in {"удалить", "заменить", "ничего не делать"}:
                raise ValueError("Неизвестное действие.")
            if not str(text).strip():
                raise ValueError("Пустой текст. Подтверждать нечего.")
            new_text, phrase = apply_action(text, action)
            file_note = ""
            if path_value:
                try:
                    Path(path_value).write_text(new_text, encoding="utf-8")
                    file_note = f" Файл на диске обновлен: {path_value}."
                except OSError as exc:
                    file_note = f" Файл на диске не изменен: {exc}."
            log_user_action(phrase + file_note)
            text = "" if action == "удалить" else new_text
            applied = phrase + file_note
            path_value = ""
        except ValueError as exc:
            error = str(exc)
        except OSError as exc:
            error = f"Не удалось записать результат: {exc}"
    elif request.method == "POST":
        try:
            sample_id = request.form.get("sample", "").strip()
            upload = request.files.get("upload")
            if sample_id:
                chosen = next(item for item in SAMPLES if str(item["id"]) == sample_id)
                text = chosen["text"]
                source = chosen["title"]
            elif path_value:
                text = read_text_file(path_value)
                source = path_value
            elif upload and upload.filename:
                raw = upload.read()
                if not raw:
                    raise ValueError("Загруженный файл пустой.")
                text = raw.decode("utf-8-sig")
                if not text.strip():
                    raise ValueError("Загруженный файл пустой.")
                source = upload.filename
            if not str(text).strip():
                raise ValueError("Пустой текст. Анализ невозможен.")
            result = analyze(text, answers_from_form())
            if result["status"] != "insufficient":
                log_incident(text, result)
        except FileNotFoundError as exc:
            error = f"Файл не найден: {exc}"
        except UnicodeDecodeError:
            error = "Файл не похож на текст в UTF-8. Сохраните его как текстовый и повторите."
        except ValueError as exc:
            error = str(exc)
        except StopIteration:
            error = "Такого учебного примера нет."
        except OSError as exc:
            error = f"Не удалось прочитать файл: {exc}"
    return render_template(
        "index.html",
        error=error,
        result=result,
        text=text,
        source=source,
        samples=SAMPLES,
        applied=applied,
        path_value=path_value,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)