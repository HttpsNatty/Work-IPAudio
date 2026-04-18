document.addEventListener('DOMContentLoaded', () => {
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('file-input');
    const audioContainer = document.getElementById('audio-container');
    const audioPlayer = document.getElementById('audio-player');
    const loadingState = document.getElementById('loading-state');
    const errorToast = document.getElementById('error-toast');
    const errorMessage = document.getElementById('error-message');
    const closeErrorBtn = document.getElementById('close-error');
    const transcriptionText = document.getElementById('transcription-text');
    const durationInfo = document.getElementById('duration-info');
    const copyBtn = document.getElementById('copy-btn');
    const copyFeedback = document.getElementById('copy-feedback');

    const API_URL = '/upload';

    const savedTranscription = localStorage.getItem('ipaudio_transcription');
    if (savedTranscription) {
        transcriptionText.value = savedTranscription;
    }

    transcriptionText.addEventListener('input', () => {
        localStorage.setItem('ipaudio_transcription', transcriptionText.value);
    });

    copyBtn.addEventListener('click', () => {
        if (!transcriptionText.value) return;
        navigator.clipboard.writeText(transcriptionText.value).then(() => {
            copyFeedback.classList.remove('hidden');
            setTimeout(() => {
                copyFeedback.classList.add('hidden');
            }, 2000);
        });
    });

    closeErrorBtn.addEventListener('click', () => {
        errorToast.classList.add('hidden');
    });

    function showError(msg) {
        errorMessage.textContent = msg;
        errorToast.classList.remove('hidden');
        loadingState.classList.add('hidden');
    }

    function resetUI() {
        errorToast.classList.add('hidden');
        loadingState.classList.add('hidden');
        audioContainer.classList.add('hidden');
        durationInfo.classList.add('hidden');
        transcriptionText.value = '';
        localStorage.removeItem('ipaudio_transcription');
        audioPlayer.pause();
        audioPlayer.src = '';
    }

    // Drag and drop events
    dropzone.addEventListener('click', () => fileInput.click());

    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
    });

    dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('dragover');
    });

    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
        
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            handleFile(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files.length > 0) {
            handleFile(e.target.files[0]);
            fileInput.value = ''; // Reset input so same file can trigger change
        }
    });

    async function handleFile(file) {
        if (!file.type.startsWith('audio/') && !file.name.match(/\.(opus|mp3|wav|ogg|m4a)$/i)) {
            showError('Please upload a valid audio file (mp3, wav, opus, ogg).');
            return;
        }

        if (file.size > 10 * 1024 * 1024) {
            showError('File exceeds the 10MB limit.');
            return;
        }

        resetUI();

        const objectUrl = URL.createObjectURL(file);
        audioPlayer.src = objectUrl;
        audioContainer.classList.remove('hidden');

        await processAudio(file);
    }

    async function processAudio(file) {
        const formData = new FormData();
        formData.append('file', file);

        loadingState.classList.remove('hidden');
        
        // 5-minute timeout for transcription
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 300000);

        try {
            const response = await fetch(API_URL, {
                method: 'POST',
                body: formData,
                signal: controller.signal
            });

            clearTimeout(timeoutId);
            const data = await response.json().catch(() => null);

            if (!response.ok) {
                if (data && data.error) {
                    throw new Error(data.error);
                } else {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
            }

            if (data && data.success) {
                loadingState.classList.add('hidden');
                
                transcriptionText.value = data.transcription;
                localStorage.setItem('ipaudio_transcription', data.transcription);
                
                durationInfo.textContent = `Processed in ${data.duration}s`;
                durationInfo.classList.remove('hidden');
            } else {
                throw new Error(data?.error || 'Unknown processing error');
            }

        } catch (error) {
            clearTimeout(timeoutId);
            if (error.name === 'AbortError') {
                showError('Request timed out. The audio could not be processed in time.');
            } else {
                showError(error.message || 'Failed to connect to the backend server.');
            }
        }
    }
});
