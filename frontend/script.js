// This file controls the browser behavior.
// It handles users, PIQ form generation, recording, saved history, and results.

const apiBaseUrl = window.location.origin;

// Save references to important HTML elements so we can use them in JavaScript.
const userNameInput = document.getElementById("userNameInput");
const addUserButton = document.getElementById("addUserButton");
const userSelect = document.getElementById("userSelect");
const deleteUserButton = document.getElementById("deleteUserButton");
const userStatus = document.getElementById("userStatus");
const piqName = document.getElementById("piqName");
const piqAge = document.getElementById("piqAge");
const piqEducation = document.getElementById("piqEducation");
const piqCity = document.getElementById("piqCity");
const piqStrengths = document.getElementById("piqStrengths");
const piqWeaknesses = document.getElementById("piqWeaknesses");
const piqHobbies = document.getElementById("piqHobbies");
const piqAchievements = document.getElementById("piqAchievements");
const piqExperience = document.getElementById("piqExperience");
const piqMotivation = document.getElementById("piqMotivation");
const generateIntroButton = document.getElementById("generateIntroButton");
const copyIntroButton = document.getElementById("copyIntroButton");
const generatedIntroduction = document.getElementById("generatedIntroduction");
const generatorStatus = document.getElementById("generatorStatus");
const recentTextsList = document.getElementById("recentTextsList");
const progressChart = document.getElementById("progressChart");
const chartStatus = document.getElementById("chartStatus");
const startRecordButton = document.getElementById("startRecordButton");
const stopRecordButton = document.getElementById("stopRecordButton");
const analyzeButton = document.getElementById("analyzeButton");
const referenceText = document.getElementById("referenceText");
const recordingStatus = document.getElementById("recordingStatus");
const recordedAudioPlayer = document.getElementById("recordedAudioPlayer");
const loadingMessage = document.getElementById("loadingMessage");
const resultCard = document.getElementById("resultCard");
const scoreValue = document.getElementById("scoreValue");
const transcriptValue = document.getElementById("transcriptValue");
const mistakesList = document.getElementById("mistakesList");

let mediaStream = null;
let audioContext = null;
let processor = null;
let sourceNode = null;
let recordedChunks = [];
let recordedAudioBlob = null;
const targetSampleRate = 16000;

function getSelectedUserName() {
  return userSelect.value.trim();
}

function setUserStatus(message) {
  userStatus.textContent = message;
}

function createEmptyCard(message) {
  const item = document.createElement("div");
  item.className = "empty-card";
  item.textContent = message;
  return item;
}

function getPiqPayload() {
  return {
    name: piqName.value.trim(),
    age: piqAge.value.trim(),
    education: piqEducation.value.trim(),
    city: piqCity.value.trim(),
    strengths: piqStrengths.value.trim(),
    weaknesses: piqWeaknesses.value.trim(),
    hobbies: piqHobbies.value.trim(),
    achievements: piqAchievements.value.trim(),
    experience: piqExperience.value.trim(),
    motivation: piqMotivation.value.trim(),
  };
}

function floatTo16BitPCM(float32Array) {
  const pcm = new Int16Array(float32Array.length);
  for (let i = 0; i < float32Array.length; i += 1) {
    const sample = Math.max(-1, Math.min(1, float32Array[i]));
    pcm[i] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
  }
  return pcm;
}

function createWavBlobFromFloat32(float32Array, sampleRate) {
  const pcmData = floatTo16BitPCM(float32Array);
  const headerSize = 44;
  const dataSize = pcmData.length * 2;
  const buffer = new ArrayBuffer(headerSize + dataSize);
  const view = new DataView(buffer);

  function writeString(offset, text) {
    for (let i = 0; i < text.length; i += 1) {
      view.setUint8(offset + i, text.charCodeAt(i));
    }
  }

  writeString(0, "RIFF");
  view.setUint32(4, 36 + dataSize, true);
  writeString(8, "WAVE");
  writeString(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeString(36, "data");
  view.setUint32(40, dataSize, true);

  let offset = 44;
  for (let i = 0; i < pcmData.length; i += 1) {
    view.setInt16(offset, pcmData[i], true);
    offset += 2;
  }

  return new Blob([buffer], { type: "audio/wav" });
}

function mergeFloat32Chunks(chunks) {
  let totalLength = 0;
  chunks.forEach((chunk) => {
    totalLength += chunk.length;
  });

  const result = new Float32Array(totalLength);
  let offset = 0;
  chunks.forEach((chunk) => {
    result.set(chunk, offset);
    offset += chunk.length;
  });

  return result;
}

async function fetchUsers(selectedUserName = "") {
  const response = await fetch(`${apiBaseUrl}/api/users`);
  const data = await response.json();

  userSelect.innerHTML = "";

  if (!data.users || data.users.length === 0) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "No users yet";
    userSelect.appendChild(option);
    userSelect.disabled = true;
    deleteUserButton.disabled = true;
    setUserStatus("Create your first user to begin.");
    renderRecentTexts([]);
    drawProgressChart([]);
    return;
  }

  userSelect.disabled = false;
  deleteUserButton.disabled = false;

  data.users.forEach((userName) => {
    const option = document.createElement("option");
    option.value = userName;
    option.textContent = userName;
    userSelect.appendChild(option);
  });

  if (selectedUserName && data.users.includes(selectedUserName)) {
    userSelect.value = selectedUserName;
  }

  await loadSelectedUserProfile();
}

async function createUser() {
  const name = userNameInput.value.trim();
  if (!name) {
    alert("Please type a user name first.");
    return;
  }

  const response = await fetch(`${apiBaseUrl}/api/users`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.detail || "Could not create user.");
  }

  userNameInput.value = "";
  await fetchUsers(data.user);
  setUserStatus(`Current user: ${data.user}`);
}

async function deleteSelectedUser() {
  const selectedUserName = getSelectedUserName();
  if (!selectedUserName) {
    alert("Please choose a user first.");
    return;
  }

  const shouldDelete = window.confirm(`Delete user ${selectedUserName} and all saved progress?`);
  if (!shouldDelete) {
    return;
  }

  const response = await fetch(`${apiBaseUrl}/api/users/${encodeURIComponent(selectedUserName)}`, {
    method: "DELETE",
  });
  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.detail || "Could not delete user.");
  }

  resultCard.classList.add("hidden");
  recordedAudioBlob = null;
  recordedAudioPlayer.classList.add("hidden");
  await fetchUsers();
}

function renderRecentTexts(recentTexts) {
  recentTextsList.innerHTML = "";

  if (!recentTexts || recentTexts.length === 0) {
    recentTextsList.appendChild(createEmptyCard("No recent texts saved yet."));
    return;
  }

  recentTexts.forEach((text) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "recent-text-button";
    button.textContent = text;
    button.addEventListener("click", () => {
      referenceText.value = text;
    });
    recentTextsList.appendChild(button);
  });
}

function drawProgressChart(analyses) {
  const context = progressChart.getContext("2d");
  const width = progressChart.width;
  const height = progressChart.height;

  context.clearRect(0, 0, width, height);
  context.fillStyle = "#ffffff";
  context.fillRect(0, 0, width, height);

  if (!analyses || analyses.length === 0) {
    chartStatus.textContent = "No saved practice sessions yet.";
    context.fillStyle = "#6b7280";
    context.font = "18px Trebuchet MS";
    context.fillText("Record and analyze speech to build your graph.", 40, height / 2);
    return;
  }

  chartStatus.textContent = `Showing ${analyses.length} saved session(s).`;

  const paddingLeft = 50;
  const paddingRight = 20;
  const paddingTop = 20;
  const paddingBottom = 40;
  const chartWidth = width - paddingLeft - paddingRight;
  const chartHeight = height - paddingTop - paddingBottom;

  context.strokeStyle = "#cbd5e1";
  context.lineWidth = 1;

  for (let score = 0; score <= 100; score += 25) {
    const y = paddingTop + chartHeight - (score / 100) * chartHeight;
    context.beginPath();
    context.moveTo(paddingLeft, y);
    context.lineTo(width - paddingRight, y);
    context.stroke();

    context.fillStyle = "#64748b";
    context.font = "12px Trebuchet MS";
    context.fillText(String(score), 14, y + 4);
  }

  context.strokeStyle = "#1d4ed8";
  context.lineWidth = 3;
  context.beginPath();

  analyses.forEach((analysis, index) => {
    const x = analyses.length === 1
      ? paddingLeft + chartWidth / 2
      : paddingLeft + (index / (analyses.length - 1)) * chartWidth;
    const y = paddingTop + chartHeight - (analysis.score / 100) * chartHeight;

    if (index === 0) {
      context.moveTo(x, y);
    } else {
      context.lineTo(x, y);
    }
  });

  context.stroke();

  analyses.forEach((analysis, index) => {
    const x = analyses.length === 1
      ? paddingLeft + chartWidth / 2
      : paddingLeft + (index / (analyses.length - 1)) * chartWidth;
    const y = paddingTop + chartHeight - (analysis.score / 100) * chartHeight;

    context.fillStyle = "#1d4ed8";
    context.beginPath();
    context.arc(x, y, 5, 0, Math.PI * 2);
    context.fill();

    context.fillStyle = "#1f2937";
    context.font = "12px Trebuchet MS";
    context.fillText(String(analysis.score), x - 10, y - 12);
  });

  context.fillStyle = "#64748b";
  context.font = "12px Trebuchet MS";
  context.fillText("Oldest", paddingLeft, height - 12);
  context.fillText("Newest", width - 60, height - 12);
}

function showMistakes(errors) {
  mistakesList.innerHTML = "";

  if (!errors || errors.length === 0) {
    const success = document.createElement("div");
    success.className = "mistake-item";
    success.style.background = "#dcfce7";
    success.style.color = "#166534";
    success.style.borderColor = "#bbf7d0";
    success.textContent = "Great job! No word-level mistakes were found.";
    mistakesList.appendChild(success);
    return;
  }

  errors.forEach((error) => {
    const item = document.createElement("div");
    item.className = "mistake-item";

    const mismatchLine = document.createElement("div");
    mismatchLine.textContent = `Expected: "${error.expected}" | Spoken: "${error.spoken}"`;
    item.appendChild(mismatchLine);

    if (error.suggestion) {
      const suggestionLine = document.createElement("div");
      suggestionLine.style.marginTop = "8px";
      suggestionLine.style.fontSize = "0.95rem";
      suggestionLine.style.color = "#7f1d1d";
      suggestionLine.textContent = `Suggestion: ${error.suggestion}`;
      item.appendChild(suggestionLine);
    }

    mistakesList.appendChild(item);
  });
}

async function loadSelectedUserProfile() {
  const selectedUserName = getSelectedUserName();
  if (!selectedUserName) {
    setUserStatus("Create your first user to begin.");
    renderRecentTexts([]);
    drawProgressChart([]);
    return;
  }

  const response = await fetch(`${apiBaseUrl}/api/users/${encodeURIComponent(selectedUserName)}`);
  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.detail || "Could not load user profile.");
  }

  setUserStatus(`Current user: ${data.name}`);
  renderRecentTexts(data.recent_texts || []);
  drawProgressChart(data.analyses || []);
}

async function generateIntroductionFromPiq() {
  const payload = getPiqPayload();
  generatorStatus.textContent = "Generating a self-introduction on the local server...";
  generateIntroButton.disabled = true;
  copyIntroButton.disabled = true;

  try {
    const response = await fetch(`${apiBaseUrl}/api/generate-introduction`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Could not generate the introduction.");
    }

    generatedIntroduction.value = data.generated_text;
    copyIntroButton.disabled = false;
    generatorStatus.textContent = "Self-introduction generated successfully. You can now move it into the pronunciation box.";
  } catch (error) {
    generatedIntroduction.value = "";
    generatorStatus.textContent = `Generation failed: ${error.message}`;
    throw error;
  } finally {
    generateIntroButton.disabled = false;
  }
}

function copyGeneratedIntroductionToReference() {
  if (!generatedIntroduction.value.trim()) {
    alert("Please generate a self-introduction first.");
    return;
  }

  referenceText.value = generatedIntroduction.value.trim();
}

async function startRecording() {
  mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: targetSampleRate });

  sourceNode = audioContext.createMediaStreamSource(mediaStream);
  processor = audioContext.createScriptProcessor(4096, 1, 1);
  recordedChunks = [];
  recordedAudioBlob = null;
  recordedAudioPlayer.classList.add("hidden");

  processor.onaudioprocess = (event) => {
    const channelData = event.inputBuffer.getChannelData(0);
    recordedChunks.push(new Float32Array(channelData));
  };

  sourceNode.connect(processor);
  processor.connect(audioContext.destination);

  recordingStatus.textContent = "Recording status: Recording now...";
  startRecordButton.disabled = true;
  stopRecordButton.disabled = false;
}

async function stopRecording() {
  if (processor) {
    processor.disconnect();
  }

  if (sourceNode) {
    sourceNode.disconnect();
  }

  if (mediaStream) {
    mediaStream.getTracks().forEach((track) => track.stop());
  }

  if (audioContext) {
    await audioContext.close();
  }

  const mergedAudio = mergeFloat32Chunks(recordedChunks);
  recordedAudioBlob = createWavBlobFromFloat32(mergedAudio, targetSampleRate);

  const audioUrl = URL.createObjectURL(recordedAudioBlob);
  recordedAudioPlayer.src = audioUrl;
  recordedAudioPlayer.classList.remove("hidden");

  recordingStatus.textContent = "Recording status: Recording saved";
  startRecordButton.disabled = false;
  stopRecordButton.disabled = true;
}

async function analyzePronunciation() {
  resultCard.classList.add("hidden");

  const selectedUserName = getSelectedUserName();
  const typedReferenceText = referenceText.value.trim();

  if (!selectedUserName) {
    alert("Please create or choose a user first.");
    return;
  }

  if (!typedReferenceText) {
    alert("Please enter a reference paragraph first.");
    return;
  }

  if (!recordedAudioBlob) {
    alert("Please record audio first.");
    return;
  }

  const formData = new FormData();
  formData.append("audio", new File([recordedAudioBlob], "recorded_audio.wav", { type: "audio/wav" }));
  formData.append("reference_text", typedReferenceText);
  formData.append("user_name", selectedUserName);

  loadingMessage.classList.remove("hidden");
  analyzeButton.disabled = true;

  try {
    const response = await fetch(`${apiBaseUrl}/api/analyze`, {
      method: "POST",
      body: formData,
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Unknown error");
    }

    scoreValue.textContent = `${data.score}/100`;
    transcriptValue.textContent = data.transcript;
    showMistakes(data.errors);
    resultCard.classList.remove("hidden");
    await loadSelectedUserProfile();
  } catch (error) {
    alert(`Analysis failed: ${error.message}`);
  } finally {
    loadingMessage.classList.add("hidden");
    analyzeButton.disabled = false;
  }
}

addUserButton.addEventListener("click", async () => {
  try {
    await createUser();
  } catch (error) {
    alert(error.message);
  }
});

deleteUserButton.addEventListener("click", async () => {
  try {
    await deleteSelectedUser();
  } catch (error) {
    alert(error.message);
  }
});

userSelect.addEventListener("change", async () => {
  try {
    await loadSelectedUserProfile();
  } catch (error) {
    alert(error.message);
  }
});

generateIntroButton.addEventListener("click", async () => {
  try {
    await generateIntroductionFromPiq();
  } catch (error) {
    alert(error.message);
  }
});

copyIntroButton.addEventListener("click", copyGeneratedIntroductionToReference);
startRecordButton.addEventListener("click", startRecording);
stopRecordButton.addEventListener("click", stopRecording);
analyzeButton.addEventListener("click", analyzePronunciation);

fetchUsers().catch((error) => {
  alert(`Could not load saved users: ${error.message}`);
});
