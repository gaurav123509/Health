const page = document.body.dataset.page;

const state = {
    language: localStorage.getItem("healthcare-language") || "en",
    city: localStorage.getItem("healthcare-city") || "Delhi",
    user: null,
    typingNode: null,
    recognition: null,
};

function setButtonLoading(button, isLoading) {
    if (!button) {
        return;
    }

    button.classList.toggle("is-loading", isLoading);
    button.disabled = isLoading;
}

async function apiRequest(url, options = {}) {
    const config = { ...options };
    const isFormData = config.body instanceof FormData;
    config.headers = {
        ...(options.headers || {}),
    };

    if (!isFormData) {
        config.headers["Content-Type"] = "application/json";
    }

    const response = await fetch(url, config);
    let payload = {};

    try {
        payload = await response.json();
    } catch (error) {
        payload = {};
    }

    if (response.status === 401 && page === "dashboard") {
        window.location.href = "/";
        throw new Error("Your session has expired.");
    }

    return { response, payload };
}

function setFeedback(node, message, type = "success") {
    if (!node) {
        return;
    }

    node.textContent = message;
    node.className = `${node.className.split(" ")[0]} ${type}`;
}

function formatDateTime(value) {
    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
        return value || "";
    }

    return date.toLocaleString([], {
        dateStyle: "medium",
        timeStyle: "short",
    });
}

function createTypingIndicator() {
    const row = document.createElement("article");
    row.className = "message-row bot";

    const avatar = document.createElement("div");
    avatar.className = "message-avatar bot";
    const img = document.createElement("img");
    img.src = document.getElementById("assistant-avatar-image").src;
    img.alt = "Bot avatar";
    avatar.appendChild(img);

    const shell = document.createElement("div");
    shell.className = "message-bubble-shell";

    const bubble = document.createElement("div");
    bubble.className = "message-bubble";

    const typing = document.createElement("div");
    typing.className = "typing-bubble";
    typing.innerHTML = "<span></span><span></span><span></span>";
    bubble.appendChild(typing);

    shell.appendChild(bubble);
    row.append(avatar, shell);
    state.typingNode = row;
    return row;
}

function removeTypingIndicator() {
    if (state.typingNode) {
        state.typingNode.remove();
        state.typingNode = null;
    }
}

function initialsForName(name) {
    const parts = String(name || "U")
        .trim()
        .split(/\s+/)
        .slice(0, 2);

    return parts.map((part) => part[0]?.toUpperCase() || "").join("") || "U";
}

function buildMeta(payload) {
    const parts = [];

    if (payload.response_source === "groq") {
        parts.push("Powered by Groq");
    } else if (payload.response_source === "groq_vision") {
        parts.push("Powered by Groq Vision");
    } else if (payload.response_source === "local_unavailable") {
        parts.push("Vision fallback");
    }

    if (payload.doctor) {
        parts.push(`Doctor: ${payload.doctor}`);
    }

    if (payload.severity && payload.severity !== "info") {
        parts.push(`Severity: ${payload.severity}`);
    }

    return parts.join(" • ");
}

function appendMessage(container, { role, text, meta = "", emergency = false, timestamp = "" }) {
    const row = document.createElement("article");
    row.className = `message-row ${role === "assistant" ? "bot" : "user"}${emergency ? " emergency" : ""}`;

    const avatar = document.createElement("div");
    avatar.className = `message-avatar ${role === "assistant" ? "bot" : "user"}`;

    if (role === "assistant") {
        const img = document.createElement("img");
        img.src = document.getElementById("assistant-avatar-image").src;
        img.alt = "Bot avatar";
        avatar.appendChild(img);
    } else {
        avatar.textContent = initialsForName(state.user?.full_name);
    }

    const shell = document.createElement("div");
    shell.className = "message-bubble-shell";

    const bubble = document.createElement("div");
    bubble.className = "message-bubble";
    bubble.textContent = text;

    const metaNode = document.createElement("div");
    metaNode.className = "message-meta";
    metaNode.textContent = [meta, formatDateTime(timestamp)].filter(Boolean).join(" • ");

    shell.append(bubble, metaNode);

    if (role === "assistant") {
        row.append(avatar, shell);
    } else {
        row.append(shell, avatar);
    }

    container.appendChild(row);
    container.scrollTop = container.scrollHeight;
}

function renderStats(stats, user) {
    document.getElementById("stat-messages").textContent = stats.total_messages;
    document.getElementById("stat-pending").textContent = stats.pending_reminders;
    document.getElementById("stat-completed").textContent = stats.completed_reminders;
    document.getElementById("stat-city").textContent = user.city || "Delhi";
}

function renderProfile(user) {
    state.user = user;
    document.getElementById("welcome-heading").textContent = `Welcome back, ${user.full_name}`;
    document.getElementById("sidebar-user-name").textContent = user.full_name;
    document.getElementById("sidebar-user-email").textContent = user.email;
    document.getElementById("profile-avatar").textContent = initialsForName(user.full_name);
    document.getElementById("topbar-profile-avatar").textContent = initialsForName(user.full_name);
    document.getElementById("topbar-profile-name").textContent = user.full_name;
    document.getElementById("profile-name").value = user.full_name || "";
    document.getElementById("profile-email").value = user.email || "";
    document.getElementById("profile-age").value = user.age || "";
    document.getElementById("profile-gender").value = user.gender || "";
    document.getElementById("profile-city").value = user.city || "Delhi";
    document.getElementById("profile-phone").value = user.phone || "";
    document.getElementById("profile-conditions").value = user.medical_conditions || "";
    document.getElementById("profile-bio").value = user.bio || "";

    if (!state.city) {
        state.city = user.city || "Delhi";
    }
    localStorage.setItem("healthcare-city", state.city);
    document.getElementById("city-select").value = state.city;
}

function syncBodyOverlayState() {
    const overlayIds = ["profile-drawer", "assistant-overlay"];
    const hasOpenOverlay = overlayIds.some((id) => {
        const node = document.getElementById(id);
        return node && !node.classList.contains("hidden");
    });

    document.body.classList.toggle("drawer-open", hasOpenOverlay);
}

function openProfileDrawer() {
    const drawer = document.getElementById("profile-drawer");
    if (!drawer) {
        return;
    }

    drawer.classList.remove("hidden");
    drawer.setAttribute("aria-hidden", "false");
    syncBodyOverlayState();
    document.getElementById("profile-feedback").textContent = "";
}

function closeProfileDrawer() {
    const drawer = document.getElementById("profile-drawer");
    if (!drawer) {
        return;
    }

    drawer.classList.add("hidden");
    drawer.setAttribute("aria-hidden", "true");
    syncBodyOverlayState();
}

function setupProfileDrawer() {
    const drawer = document.getElementById("profile-drawer");
    const closeButton = document.getElementById("close-profile-button");

    document.querySelectorAll(".profile-trigger").forEach((button) => {
        button.addEventListener("click", openProfileDrawer);
    });

    closeButton.addEventListener("click", closeProfileDrawer);

    drawer.addEventListener("click", (event) => {
        if (event.target === drawer) {
            closeProfileDrawer();
        }
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            closeProfileDrawer();
        }
    });
}

function openAssistantOverlay() {
    const overlay = document.getElementById("assistant-overlay");
    if (!overlay) {
        return;
    }

    overlay.classList.remove("hidden");
    overlay.setAttribute("aria-hidden", "false");
    syncBodyOverlayState();
    window.setTimeout(() => {
        document.getElementById("chat-input")?.focus();
    }, 60);
}

function closeAssistantOverlay() {
    const overlay = document.getElementById("assistant-overlay");
    if (!overlay) {
        return;
    }

    overlay.classList.add("hidden");
    overlay.setAttribute("aria-hidden", "true");
    syncBodyOverlayState();
}

async function launchAssistantWithPrompt(message) {
    openAssistantOverlay();
    await sendMessage(message);
}

function setupAssistantOverlay() {
    const overlay = document.getElementById("assistant-overlay");
    const closeButton = document.getElementById("close-assistant-button");
    const uploadButton = document.getElementById("upload-medicine-button");
    const imageInput = document.getElementById("medicine-image-input");

    document.querySelectorAll(".assistant-trigger").forEach((button) => {
        button.addEventListener("click", openAssistantOverlay);
    });

    document.querySelectorAll(".assistant-prompt").forEach((button) => {
        button.addEventListener("click", async () => {
            await launchAssistantWithPrompt(button.dataset.prompt);
        });
    });

    closeButton.addEventListener("click", closeAssistantOverlay);

    uploadButton.addEventListener("click", () => {
        imageInput.click();
    });

    imageInput.addEventListener("change", async (event) => {
        const [file] = event.target.files || [];
        await analyzeMedicineImage(file);
    });

    overlay.addEventListener("click", (event) => {
        if (event.target === overlay) {
            closeAssistantOverlay();
        }
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            closeAssistantOverlay();
        }
    });
}

function renderTip(tip) {
    document.getElementById("tip-category").textContent = tip.category || "Health Tip";
    document.getElementById("tip-text").textContent = tip.tip || "";
}

function renderReminders(reminders) {
    const list = document.getElementById("reminder-list");
    list.innerHTML = "";

    if (!reminders.length) {
        const empty = document.createElement("div");
        empty.className = "empty-state";
        empty.textContent = "No reminders saved yet.";
        list.appendChild(empty);
        return;
    }

    reminders.forEach((reminder) => {
        const item = document.createElement("article");
        item.className = `reminder-item${reminder.is_completed ? " completed" : ""}`;

        const title = document.createElement("h4");
        title.textContent = reminder.medicine_name;

        const time = document.createElement("p");
        time.textContent = formatDateTime(reminder.time);

        const notes = document.createElement("p");
        notes.textContent = reminder.notes || "No additional notes.";

        const footer = document.createElement("div");
        footer.className = "reminder-footer";

        const status = document.createElement("span");
        status.textContent = reminder.is_completed ? "Completed" : "Pending";

        const actions = document.createElement("div");
        actions.className = "reminder-actions";

        if (!reminder.is_completed) {
            const completeButton = document.createElement("button");
            completeButton.type = "button";
            completeButton.className = "reminder-button complete";
            completeButton.textContent = "Mark Done";
            completeButton.addEventListener("click", async () => {
                await completeReminder(reminder.id);
            });
            actions.appendChild(completeButton);
        }

        const deleteButton = document.createElement("button");
        deleteButton.type = "button";
        deleteButton.className = "reminder-button delete";
        deleteButton.textContent = "Delete";
        deleteButton.addEventListener("click", async () => {
            await deleteReminder(reminder.id);
        });
        actions.appendChild(deleteButton);

        footer.append(status, actions);
        item.append(title, time, notes, footer);
        list.appendChild(item);
    });
}

function renderHospitals(hospitals, note) {
    document.getElementById("hospital-note").textContent = note || "Nearby hospitals";
    const list = document.getElementById("hospital-list");
    list.innerHTML = "";

    if (!hospitals.length) {
        const empty = document.createElement("div");
        empty.className = "empty-state";
        empty.textContent = "No curated hospital suggestions found for this city.";
        list.appendChild(empty);
        return;
    }

    hospitals.forEach((hospital) => {
        const item = document.createElement("article");
        item.className = "hospital-item";

        const content = document.createElement("div");
        const title = document.createElement("h4");
        title.textContent = hospital.name;
        const specialty = document.createElement("p");
        specialty.textContent = hospital.specialty;
        const area = document.createElement("p");
        area.textContent = hospital.area;
        content.append(title, specialty, area);

        item.appendChild(content);
        list.appendChild(item);
    });
}

function showEmergency(text) {
    const banner = document.getElementById("emergency-banner");
    document.getElementById("emergency-banner-text").textContent = text;
    banner.classList.remove("hidden");
}

function hideEmergency() {
    document.getElementById("emergency-banner").classList.add("hidden");
}

async function loadDashboard() {
    const { response, payload } = await apiRequest(
        `/api/dashboard?language=${encodeURIComponent(state.language)}&city=${encodeURIComponent(state.city)}`
    );

    if (!response.ok) {
        throw new Error(payload.error || "Dashboard could not be loaded.");
    }

    renderProfile(payload.user);
    renderStats(payload.stats, payload.user);
    renderTip(payload.tip);
    renderReminders(payload.reminders);
    renderHospitals(payload.hospitals, payload.hospital_note);
}

async function loadChatHistory() {
    const container = document.getElementById("chat-messages");
    container.innerHTML = "";

    const { response, payload } = await apiRequest("/api/chat/history");
    if (!response.ok) {
        throw new Error(payload.error || "Chat history could not be loaded.");
    }

    if (!payload.messages.length) {
        appendMessage(container, {
            role: "assistant",
            text: "Hello, I’m ready to help. Tell me about your symptoms, ask for guidance, or upload a tablet photo to extract medicine details.",
            meta: "CareGuide Copilot",
            timestamp: new Date().toISOString(),
        });
        return;
    }

    payload.messages.forEach((message) => {
        appendMessage(container, {
            role: message.role,
            text: message.message,
            timestamp: message.created_at,
        });
    });
}

async function loadHospitals() {
    const { response, payload } = await apiRequest(
        `/api/hospitals?city=${encodeURIComponent(state.city)}&language=${encodeURIComponent(state.language)}`
    );

    if (!response.ok) {
        throw new Error(payload.error || "Hospitals could not be loaded.");
    }

    renderHospitals(payload.hospitals, payload.note);
}

async function refreshTip() {
    const button = document.getElementById("refresh-tip-button");
    setButtonLoading(button, true);

    try {
        const { response, payload } = await apiRequest(
            `/api/tips?language=${encodeURIComponent(state.language)}`
        );
        if (!response.ok) {
            throw new Error(payload.error || "Tip could not be loaded.");
        }
        renderTip(payload);
    } catch (error) {
        document.getElementById("tip-text").textContent = error.message;
    } finally {
        setButtonLoading(button, false);
    }
}

async function sendMessage(message) {
    const container = document.getElementById("chat-messages");
    hideEmergency();
    appendMessage(container, {
        role: "user",
        text: message,
        timestamp: new Date().toISOString(),
    });

    const typingNode = createTypingIndicator();
    container.appendChild(typingNode);
    container.scrollTop = container.scrollHeight;
    document.getElementById("chat-input").value = "";

    const button = document.getElementById("send-button");
    setButtonLoading(button, true);

    try {
        const { response, payload } = await apiRequest("/api/chat", {
            method: "POST",
            body: JSON.stringify({
                message,
                language: state.language,
                city: state.city,
            }),
        });

        removeTypingIndicator();

        if (!response.ok) {
            throw new Error(payload.error || "The assistant could not answer right now.");
        }

        appendMessage(container, {
            role: "assistant",
            text: payload.response,
            meta: buildMeta(payload),
            emergency: payload.emergency,
            timestamp: new Date().toISOString(),
        });

        if (payload.emergency) {
            showEmergency(payload.follow_up || payload.response);
        }

        const messageStat = document.getElementById("stat-messages");
        messageStat.textContent = String(Number(messageStat.textContent || "0") + 2);
    } catch (error) {
        removeTypingIndicator();
        appendMessage(container, {
            role: "assistant",
            text: error.message,
            meta: "System",
            timestamp: new Date().toISOString(),
        });
    } finally {
        setButtonLoading(button, false);
    }
}

async function analyzeMedicineImage(file) {
    if (!file) {
        return;
    }

    openAssistantOverlay();
    hideEmergency();

    const container = document.getElementById("chat-messages");
    const uploadButton = document.getElementById("upload-medicine-button");
    const status = document.getElementById("image-upload-status");
    const imageInput = document.getElementById("medicine-image-input");

    appendMessage(container, {
        role: "user",
        text: `Uploaded medicine photo: ${file.name}`,
        meta: "Image upload",
        timestamp: new Date().toISOString(),
    });

    const typingNode = createTypingIndicator();
    container.appendChild(typingNode);
    container.scrollTop = container.scrollHeight;
    setButtonLoading(uploadButton, true);
    status.textContent = "Analyzing medicine photo...";

    try {
        const formData = new FormData();
        formData.append("image", file);
        formData.append("language", state.language);
        formData.append("city", state.city);

        const { response, payload } = await apiRequest("/api/chat/medicine-image", {
            method: "POST",
            body: formData,
        });

        removeTypingIndicator();

        if (!response.ok) {
            throw new Error(payload.error || "Medicine image could not be analyzed.");
        }

        appendMessage(container, {
            role: "assistant",
            text: payload.response,
            meta: buildMeta(payload),
            timestamp: new Date().toISOString(),
        });

        status.textContent = "Medicine details extracted. You can upload another photo anytime.";
        const messageStat = document.getElementById("stat-messages");
        messageStat.textContent = String(Number(messageStat.textContent || "0") + 2);
    } catch (error) {
        removeTypingIndicator();
        appendMessage(container, {
            role: "assistant",
            text: error.message,
            meta: "System",
            timestamp: new Date().toISOString(),
        });
        status.textContent = error.message;
    } finally {
        setButtonLoading(uploadButton, false);
        imageInput.value = "";
    }
}

async function saveProfile(event) {
    event.preventDefault();
    const button = document.getElementById("profile-button");
    setButtonLoading(button, true);

    try {
        const { response, payload } = await apiRequest("/api/profile", {
            method: "PUT",
            body: JSON.stringify({
                full_name: document.getElementById("profile-name").value.trim(),
                age: document.getElementById("profile-age").value,
                gender: document.getElementById("profile-gender").value,
                city: document.getElementById("profile-city").value,
                phone: document.getElementById("profile-phone").value.trim(),
                medical_conditions: document.getElementById("profile-conditions").value.trim(),
                bio: document.getElementById("profile-bio").value.trim(),
            }),
        });

        if (!response.ok) {
            throw new Error(payload.error || "Profile could not be updated.");
        }

        state.city = payload.user.city || state.city;
        localStorage.setItem("healthcare-city", state.city);
        renderProfile(payload.user);
        renderStats(
            {
                total_messages: Number(document.getElementById("stat-messages").textContent || "0"),
                pending_reminders: Number(document.getElementById("stat-pending").textContent || "0"),
                completed_reminders: Number(document.getElementById("stat-completed").textContent || "0"),
            },
            payload.user
        );
        await loadHospitals();
        setFeedback(document.getElementById("profile-feedback"), payload.message, "success");
    } catch (error) {
        setFeedback(document.getElementById("profile-feedback"), error.message, "error");
    } finally {
        setButtonLoading(button, false);
    }
}

async function submitBMI(event) {
    event.preventDefault();
    const button = document.getElementById("bmi-button");
    setButtonLoading(button, true);

    try {
        const { response, payload } = await apiRequest("/api/bmi", {
            method: "POST",
            body: JSON.stringify({
                height: document.getElementById("height-input").value,
                weight: document.getElementById("weight-input").value,
                language: state.language,
            }),
        });

        if (!response.ok) {
            throw new Error(payload.error || "BMI could not be calculated.");
        }

        document.getElementById("bmi-result").textContent = `${payload.category} • BMI ${payload.bmi}. ${payload.advice}`;
    } catch (error) {
        document.getElementById("bmi-result").textContent = error.message;
    } finally {
        setButtonLoading(button, false);
    }
}

async function saveReminder(event) {
    event.preventDefault();
    const button = document.getElementById("reminder-button");
    setButtonLoading(button, true);

    try {
        const { response, payload } = await apiRequest("/api/reminders", {
            method: "POST",
            body: JSON.stringify({
                medicine_name: document.getElementById("medicine-input").value.trim(),
                time: document.getElementById("reminder-time-input").value,
                notes: document.getElementById("notes-input").value.trim(),
                language: state.language,
            }),
        });

        if (!response.ok) {
            throw new Error(payload.error || "Reminder could not be created.");
        }

        document.getElementById("reminder-form").reset();
        setFeedback(document.getElementById("reminder-feedback"), payload.message, "success");
        await loadDashboard();
    } catch (error) {
        setFeedback(document.getElementById("reminder-feedback"), error.message, "error");
    } finally {
        setButtonLoading(button, false);
    }
}

async function completeReminder(reminderId) {
    const { response, payload } = await apiRequest(
        `/api/reminders/${reminderId}/complete?language=${encodeURIComponent(state.language)}`,
        { method: "POST" }
    );

    if (!response.ok) {
        setFeedback(document.getElementById("reminder-feedback"), payload.error || "Reminder could not be updated.", "error");
        return;
    }

    setFeedback(document.getElementById("reminder-feedback"), payload.message, "success");
    await loadDashboard();
}

async function deleteReminder(reminderId) {
    const { response, payload } = await apiRequest(
        `/api/reminders/${reminderId}?language=${encodeURIComponent(state.language)}`,
        { method: "DELETE" }
    );

    if (!response.ok) {
        setFeedback(document.getElementById("reminder-feedback"), payload.error || "Reminder could not be deleted.", "error");
        return;
    }

    setFeedback(document.getElementById("reminder-feedback"), payload.message, "success");
    await loadDashboard();
}

function setupVoiceRecognition() {
    const voiceButton = document.getElementById("voice-button");
    const voiceStatus = document.getElementById("voice-status");
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!Recognition) {
        voiceButton.disabled = true;
        voiceStatus.textContent = "Voice input is not supported in this browser.";
        return;
    }

    const recognition = new Recognition();
    recognition.interimResults = true;
    recognition.continuous = false;

    recognition.onstart = () => {
        voiceButton.classList.add("listening");
        voiceStatus.textContent = "Listening...";
    };

    recognition.onend = () => {
        voiceButton.classList.remove("listening");
        voiceStatus.textContent = "Voice input ready.";
    };

    recognition.onerror = () => {
        voiceButton.classList.remove("listening");
        voiceStatus.textContent = "Voice input failed. Try again.";
    };

    recognition.onresult = (event) => {
        let transcript = "";

        for (let index = event.resultIndex; index < event.results.length; index += 1) {
            transcript += event.results[index][0].transcript;
        }

        document.getElementById("chat-input").value = transcript.trim();
    };

    voiceButton.addEventListener("click", () => {
        recognition.lang = state.language === "hi" ? "hi-IN" : "en-IN";
        recognition.start();
    });

    state.recognition = recognition;
}

async function logout() {
    await apiRequest("/api/auth/logout", { method: "POST" });
    window.location.href = "/";
}

function initAuthPage() {
    const loginForm = document.getElementById("login-form");
    const registerForm = document.getElementById("register-form");
    const showLogin = document.getElementById("show-login");
    const showRegister = document.getElementById("show-register");
    const feedback = document.getElementById("auth-feedback");

    function toggleAuth(mode) {
        const loginMode = mode === "login";
        loginForm.classList.toggle("hidden", !loginMode);
        registerForm.classList.toggle("hidden", loginMode);
        showLogin.classList.toggle("active", loginMode);
        showRegister.classList.toggle("active", !loginMode);
        feedback.textContent = "";
        feedback.className = "auth-feedback";
    }

    showLogin.addEventListener("click", () => toggleAuth("login"));
    showRegister.addEventListener("click", () => toggleAuth("register"));

    loginForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const button = document.getElementById("login-button");
        setButtonLoading(button, true);

        try {
            const { response, payload } = await apiRequest("/api/auth/login", {
                method: "POST",
                body: JSON.stringify({
                    email: document.getElementById("login-email").value.trim(),
                    password: document.getElementById("login-password").value,
                }),
            });

            if (!response.ok) {
                throw new Error(payload.error || "Login failed.");
            }

            setFeedback(feedback, payload.message, "success");
            window.location.href = "/dashboard";
        } catch (error) {
            setFeedback(feedback, error.message, "error");
        } finally {
            setButtonLoading(button, false);
        }
    });

    registerForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const button = document.getElementById("register-button");
        setButtonLoading(button, true);

        try {
            const { response, payload } = await apiRequest("/api/auth/register", {
                method: "POST",
                body: JSON.stringify({
                    full_name: document.getElementById("register-name").value.trim(),
                    email: document.getElementById("register-email").value.trim(),
                    password: document.getElementById("register-password").value,
                    city: document.getElementById("register-city").value,
                }),
            });

            if (!response.ok) {
                throw new Error(payload.error || "Account creation failed.");
            }

            setFeedback(feedback, payload.message, "success");
            window.location.href = "/dashboard";
        } catch (error) {
            setFeedback(feedback, error.message, "error");
        } finally {
            setButtonLoading(button, false);
        }
    });
}

async function initDashboardPage() {
    document.getElementById("language-select").value = state.language;
    document.getElementById("city-select").value = state.city;
    document.getElementById("profile-city").value = state.city;

    await Promise.all([loadDashboard(), loadChatHistory()]);
    setupVoiceRecognition();
    setupProfileDrawer();
    setupAssistantOverlay();

    document.getElementById("language-select").addEventListener("change", async (event) => {
        state.language = event.target.value;
        localStorage.setItem("healthcare-language", state.language);
        await Promise.all([loadDashboard(), loadChatHistory()]);
    });

    document.getElementById("city-select").addEventListener("change", async (event) => {
        state.city = event.target.value;
        localStorage.setItem("healthcare-city", state.city);
        document.getElementById("profile-city").value = state.city;
        await loadHospitals();
    });

    document.getElementById("chat-form").addEventListener("submit", async (event) => {
        event.preventDefault();
        const message = document.getElementById("chat-input").value.trim();
        if (!message) {
            return;
        }
        await sendMessage(message);
    });

    document.getElementById("profile-form").addEventListener("submit", saveProfile);
    document.getElementById("bmi-form").addEventListener("submit", submitBMI);
    document.getElementById("reminder-form").addEventListener("submit", saveReminder);
    document.getElementById("refresh-tip-button").addEventListener("click", refreshTip);
    document.getElementById("logout-button").addEventListener("click", logout);
}

if (page === "auth") {
    initAuthPage();
}

if (page === "dashboard") {
    initDashboardPage();
}
