const form = document.getElementById('upload-form');
const resultImg = document.getElementById('result-img');
const info = document.getElementById('info');
const cameraButton = document.getElementById('camera-button');
const cameraOverlay = document.getElementById('camera-overlay');
const video = document.getElementById('camera-video');
const captureBtn = document.getElementById('capture-btn');
const closeBtn = document.getElementById('close-btn');

let stream = null;
let currentLat = null;
let currentLon = null;

// --- Request geolocation as soon as page loads ---
if (navigator.geolocation) {
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      currentLat = pos.coords.latitude;
      currentLon = pos.coords.longitude;
      console.log("✅ Location acquired:", currentLat, currentLon);
    },
    (err) => {
      console.warn("⚠️ Could not get location:", err.message);
    }
  );
} else {
  console.warn("❌ Geolocation not supported in this browser.");
}

// --- Helper to send image to backend ---
async function sendImage(formData) {
  // Attach geolocation if available
  if (currentLat && currentLon) {
    formData.append('latitude', currentLat);
    formData.append('longitude', currentLon);
  }
  info.textContent = "Processing...";
  resultImg.style.display = 'none';
  const response = await fetch('/upload', { method: 'POST', body: formData });
  if (response.ok) {
    const data = await response.json();
    const { image_data, total, nurdles, beads } = data;
    resultImg.src = `data:image/jpeg;base64,${image_data}`;
    resultImg.style.display = 'block';
    info.innerHTML = `
      <strong>Total detected:</strong> ${total}<br>
      🟢 <strong>Nurdles:</strong> ${nurdles}<br>
      🔵 <strong>Beads:</strong> ${beads}<br>
    `;
  } else {
    info.textContent = "Failed to process the image.";
  }
}

// --- Handle regular file uploads ---
form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const formData = new FormData(form);
  await sendImage(formData);
});

// --- Show camera overlay ---
cameraButton.addEventListener('click', async () => {
  cameraOverlay.style.display = 'flex';
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
    video.srcObject = stream;
  } catch (err) {
    alert('Error accessing camera: ' + err.message);
    cameraOverlay.style.display = 'none';
  }
});

// --- Close camera overlay ---
closeBtn.addEventListener('click', () => {
  if (stream) {
    stream.getTracks().forEach(track => track.stop());
  }
  video.srcObject = null;
  cameraOverlay.style.display = 'none';
});

// --- Capture and upload camera photo ---
captureBtn.addEventListener('click', async () => {
  if (!stream) return;
  const canvas = document.createElement('canvas');
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  canvas.toBlob(async (blob) => {
    const formData = new FormData();
    formData.append('image', blob, 'capture.jpg');
    await sendImage(formData);
    closeBtn.click();
  }, 'image/jpeg', 0.9);
});
