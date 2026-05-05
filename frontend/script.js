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
    const themeToggle = document.getElementById('theme-toggle');
    const themeIcon = document.getElementById('theme-icon');

    // Theme handling: default = light
    function setTheme(theme) {
        if (theme === 'dark') {
            document.documentElement.classList.add('dark-theme');
            // moon icon
            themeIcon.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>';
            localStorage.setItem('ipaudio_theme', 'dark');
        } else {
            document.documentElement.classList.remove('dark-theme');
            // sun icon
            themeIcon.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"></circle><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"></path></svg>';
            localStorage.setItem('ipaudio_theme', 'light');
        }
    }

    // Initialize theme from storage (default light)
    try {
        const savedTheme = localStorage.getItem('ipaudio_theme') || 'light';
        setTheme(savedTheme);
    } catch (e) {
        setTheme('light');
    }

    if (themeToggle) {
        themeToggle.addEventListener('click', () => {
            const isDark = document.documentElement.classList.contains('dark-theme');
            setTheme(isDark ? 'light' : 'dark');
        });
    }

    const API_URL = '/upload';

    // Do not auto-restore previous transcription unless an audio is loaded.
    const savedTranscription = localStorage.getItem('ipaudio_transcription');
    if (!audioContainer.classList.contains('hidden')) {
        if (savedTranscription) transcriptionText.value = savedTranscription;
    } else {
        // no audio loaded: clear stale transcription from localStorage
        localStorage.removeItem('ipaudio_transcription');
        transcriptionText.value = '';
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

        // ensure we have a progress element
        let progressEl = document.getElementById('processing-progress');
        if (!progressEl) {
            progressEl = document.createElement('div');
            progressEl.id = 'processing-progress';
            progressEl.style.marginTop = '8px';
            progressEl.textContent = 'Progress: 0%';
            loadingState.appendChild(progressEl);
        }

        try {
            const response = await fetch(API_URL, { method: 'POST', body: formData });
            const data = await response.json().catch(() => null);

            if (!response.ok || !data || !data.success) {
                throw new Error(data?.error || `HTTP error! status: ${response.status}`);
            }

            const jobId = data.job_id;
            // poll status
            let finished = false;
            const startPoll = Date.now();
            while (!finished) {
                await new Promise(r => setTimeout(r, 1000));
                const sres = await fetch(`/status/${jobId}`);
                const sdata = await sres.json().catch(() => null);
                if (!sres.ok || !sdata || !sdata.success) {
                    throw new Error(sdata?.error || `Status error: ${sres.status}`);
                }

                const job = sdata.job;
                const prog = job.progress ?? 0;
                progressEl.textContent = `Progress: ${prog}% — ${job.message || ''}`;

                if (job.status === 'done') {
                    finished = true;
                    loadingState.classList.add('hidden');
                    transcriptionText.value = job.transcription || '';
                    localStorage.setItem('ipaudio_transcription', job.transcription || '');
                    durationInfo.textContent = `Processed in ${job.duration || 0}s`;
                    durationInfo.classList.remove('hidden');
                } else if (job.status === 'error') {
                    throw new Error(job.error || job.message || 'Processing error');
                }

                // safety timeout 6 minutes
                if ((Date.now() - startPoll) > 6 * 60 * 1000) {
                    throw new Error('Processing timeout');
                }
            }

        } catch (error) {
            loadingState.classList.add('hidden');
            showError(error.message || 'Failed to process audio');
        }
    }
});
