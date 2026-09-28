(() => {
    "use strict";

    const form = document.getElementById("receipt-form");
    if (!form) return;

    const cfg = window.PROMO || {};
    const csrf = form.querySelector("[name=csrfmiddlewaretoken]").value;
    const errorsBox = document.getElementById("form-errors");
    const successBox = document.getElementById("form-success");

    // ---------- Утилиты для отображения ошибок ----------

    function setError(fieldName, message) {
        const node = form.querySelector(`[data-error-for="${fieldName}"]`);
        if (node) node.textContent = message || "";
        const input = form.querySelector(`[name="${fieldName}"]`);
        if (input) input.classList.toggle("invalid", Boolean(message));
    }

    function clearErrors() {
        form.querySelectorAll(".error").forEach((n) => { n.textContent = ""; });
        form.querySelectorAll(".input.invalid").forEach((n) => n.classList.remove("invalid"));
        if (errorsBox) { errorsBox.hidden = true; errorsBox.textContent = ""; }
        if (successBox) { successBox.hidden = true; successBox.textContent = ""; }
    }

    // ---------- Клиентские валидаторы ----------
    // Не заменяют серверные проверки, только дают быструю обратную связь.

    const validators = {
        fn: (v) => /^\d{16}$/.test(v) ? "" : "ФН — ровно 16 цифр.",
        fd: (v) => /^\d{1,10}$/.test(v) ? "" : "ФД — только цифры, до 10 знаков.",
        fp: (v) => /^\d{1,10}$/.test(v) ? "" : "ФП — только цифры, до 10 знаков.",
        amount: (v) => {
            const n = Number(String(v).replace(",", "."));
            if (!Number.isFinite(n) || n <= 0) return "Введите сумму.";
            if (n < Number(cfg.minAmount)) return `Минимум ${cfg.minAmount} руб.`;
            return "";
        },
        purchase_datetime: (v) => {
            if (!v) return "Укажите дату и время покупки.";
            const d = new Date(v);
            if (Number.isNaN(d.getTime())) return "Некорректная дата.";
            const start = new Date(cfg.start);
            const end = new Date(cfg.end);
            if (d < start || d > end) {
                const fmt = (x) => x.toLocaleString("ru-RU", {
                    day: "2-digit", month: "2-digit", year: "numeric",
                    hour: "2-digit", minute: "2-digit",
                });
                return `Дата должна быть в периоде акции: ${fmt(start)} — ${fmt(end)}.`;
            }
            return "";
        },
    };

    function validateField(name) {
        const el = form.querySelector(`[name="${name}"]`);
        if (!el || !validators[name]) return true;
        const message = validators[name](el.value.trim());
        setError(name, message);
        return !message;
    }

    form.querySelectorAll("input, textarea").forEach((el) => {
        el.addEventListener("blur", () => validateField(el.name));
        el.addEventListener("input", () => {
            if (el.classList.contains("invalid")) validateField(el.name);
        });
    });

    // ---------- QR парсер ----------

    const qrBtn = document.getElementById("qr-parse");
    const qrInput = document.getElementById("qr-input");
    const qrHint = document.getElementById("qr-hint");

    if (qrBtn && qrInput) {
        qrBtn.addEventListener("click", () => {
            qrHint.textContent = "";
            qrHint.style.color = "";
            const raw = (qrInput.value || "").trim();
            if (!raw) {
                qrHint.textContent = "Вставьте строку из QR-кода.";
                qrHint.style.color = "var(--err)";
                return;
            }
            try {
                const qs = raw.startsWith("http") && raw.includes("?")
                    ? raw.split("?", 2)[1]
                    : raw;
                const params = new URLSearchParams(qs);

                const fn = params.get("fn");
                const fd = params.get("i") || params.get("fd");
                const fp = params.get("fp");
                const s = params.get("s");
                const t = params.get("t");

                if (fn) form.fn.value = fn;
                if (fd) form.fd.value = fd;
                if (fp) form.fp.value = fp;
                if (s) form.amount.value = s.replace(",", ".");

                if (t && /^\d{8}T\d{4}/.test(t)) {
                    const y = t.slice(0, 4);
                    const mo = t.slice(4, 6);
                    const d = t.slice(6, 8);
                    const h = t.slice(9, 11);
                    const mi = t.slice(11, 13);
                    form.purchase_datetime.value = `${y}-${mo}-${d}T${h}:${mi}`;
                }

                qrHint.textContent = "Поля заполнены. Проверьте и отправьте форму.";
                qrHint.style.color = "var(--ok)";
            } catch (err) {
                qrHint.textContent = "Не удалось разобрать строку.";
                qrHint.style.color = "var(--err)";
            }
        });
    }

    // ---------- Отправка через fetch ----------

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        clearErrors();

        let valid = true;
        ["fn", "fd", "fp", "amount", "purchase_datetime"].forEach((name) => {
            if (!validateField(name)) valid = false;
        });
        if (!valid) {
            errorsBox.hidden = false;
            errorsBox.textContent = "Исправьте ошибки в форме.";
            errorsBox.scrollIntoView({ behavior: "smooth", block: "center" });
            return;
        }

        const submitBtn = form.querySelector("button[type=submit]");
        const originalText = submitBtn.textContent;
        submitBtn.disabled = true;
        submitBtn.textContent = "Отправляем...";

        try {
            const fd = new FormData(form);
            const response = await fetch(cfg.submitUrl, {
                method: "POST",
                body: fd,
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                    "X-CSRFToken": csrf,
                },
                credentials: "same-origin",
            });
            const data = await response.json();

            if (response.ok && data.ok) {
                successBox.hidden = false;
                successBox.textContent = data.message || "Чек отправлен на проверку.";
                form.reset();
                setTimeout(() => { window.location.href = cfg.cabinetUrl; }, 1200);
            } else {
                errorsBox.hidden = false;
                errorsBox.textContent = "Проверьте отмеченные поля.";

                const errors = (data && data.errors) || {};
                Object.entries(errors).forEach(([field, list]) => {
                    const message = list.map((e) => e.message).join(" ");
                    if (field === "__all__") {
                        errorsBox.textContent += " " + message;
                    } else {
                        setError(field, message);
                    }
                });
                errorsBox.scrollIntoView({ behavior: "smooth", block: "center" });
            }
        } catch (err) {
            errorsBox.hidden = false;
            errorsBox.textContent = "Сетевая ошибка. Попробуйте ещё раз.";
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = originalText;
        }
    });
})();
