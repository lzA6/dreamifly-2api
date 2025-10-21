document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const apiKeyInput = document.getElementById('api-key');
    const modelSelect = document.getElementById('model-select');
    const styleSelect = document.getElementById('style-select');
    const imageUpload = document.getElementById('image-upload');
    const imagePreviewContainer = document.getElementById('image-preview-container');
    const imagePreview = document.getElementById('image-preview');
    const uploadPlaceholder = document.getElementById('upload-placeholder');
    const clearImageBtn = document.getElementById('clear-image-btn');
    const promptInput = document.getElementById('prompt-input');
    const generateBtn = document.getElementById('generate-btn');
    
    const widthSlider = document.getElementById('width-slider');
    const widthValue = document.getElementById('width-value');
    const heightSlider = document.getElementById('height-slider');
    const heightValue = document.getElementById('height-value');
    const stepsSlider = document.getElementById('steps-slider');
    const stepsValue = document.getElementById('steps-value');
    const countSlider = document.getElementById('count-slider');
    const countValue = document.getElementById('count-value');

    const imageGrid = document.getElementById('image-grid');
    const spinner = document.getElementById('spinner');
    const errorMessage = document.getElementById('error-message');
    const placeholder = document.getElementById('placeholder');

    let selectedFile = null;

    // --- Core Functions ---

    async function fetchAndPopulate(endpoint, selectElement, placeholderText) {
        selectElement.innerHTML = `<option>${placeholderText}...</option>`;
        selectElement.disabled = true;
        
        try {
            const apiKey = apiKeyInput.value.trim();
            if (!apiKey) throw new Error("API Key is missing.");

            const response = await fetch(endpoint, { headers: { 'Authorization': `Bearer ${apiKey}` } });
            const result = await response.json();
            if (!response.ok) throw new Error(result.detail || `Failed to load data from ${endpoint}`);
            
            selectElement.innerHTML = '';
            result.data.forEach(item => {
                const option = document.createElement('option');
                const value = typeof item === 'object' ? item.id : item;
                option.value = value;
                option.textContent = value;
                selectElement.appendChild(option);
            });
            selectElement.disabled = false;
            return true;
        } catch (error) {
            selectElement.innerHTML = `<option>加载失败</option>`;
            showError(`加载失败: ${error.message}`);
            return false;
        }
    }

    async function loadInitialData() {
        generateBtn.disabled = true;
        const modelsLoaded = await fetchAndPopulate('/v1/models', modelSelect, '加载模型中');
        const stylesLoaded = await fetchAndPopulate('/v1/styles', styleSelect, '加载风格中');
        if (modelsLoaded && stylesLoaded) {
            generateBtn.disabled = false;
        }
    }

    function handleFile(file) {
        if (!file) return;
        selectedFile = file;
        const reader = new FileReader();
        reader.onload = e => {
            imagePreview.src = e.target.result;
            imagePreview.classList.remove('hidden');
            uploadPlaceholder.classList.add('hidden');
            clearImageBtn.classList.remove('hidden');
        };
        reader.readAsDataURL(file);
    }

    function clearImage() {
        selectedFile = null;
        imageUpload.value = '';
        imagePreview.src = '#';
        imagePreview.classList.add('hidden');
        uploadPlaceholder.classList.remove('hidden');
        clearImageBtn.classList.add('hidden');
    }

    async function handleGenerate() {
        const apiKey = apiKeyInput.value.trim();
        const prompt = promptInput.value.trim();
        if (!apiKey || !prompt) {
            showError("请确保 API Key 和提示词都已填写。");
            return;
        }

        setLoading(true);

        try {
            let response;
            if (selectedFile) {
                // 图生图
                const formData = new FormData();
                formData.append('image', selectedFile);
                formData.append('prompt', prompt);
                formData.append('model', modelSelect.value);
                formData.append('style', styleSelect.value);
                formData.append('n', countSlider.value);
                formData.append('size', `${widthSlider.value}x${heightSlider.value}`);
                formData.append('steps', stepsSlider.value);
                
                response = await fetch('/v1/images/edits', {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${apiKey}` },
                    body: formData
                });
            } else {
                // 文生图
                const payload = {
                    prompt: prompt,
                    model: modelSelect.value,
                    style: styleSelect.value,
                    n: parseInt(countSlider.value, 10),
                    size: `${widthSlider.value}x${heightSlider.value}`,
                    steps: parseInt(stepsSlider.value, 10),
                    response_format: "b64_json"
                };
                response = await fetch('/v1/images/generations', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${apiKey}`
                    },
                    body: JSON.stringify(payload)
                });
            }

            const result = await response.json();
            if (!response.ok) throw new Error(result.detail || '生成失败，未知错误。');

            if (result.data && result.data.length > 0) {
                displayImages(result.data);
            } else {
                throw new Error('API 返回了成功状态，但没有图片数据。');
            }
        } catch (error) {
            showError(error.message);
        } finally {
            setLoading(false);
        }
    }

    function displayImages(data) {
        imageGrid.innerHTML = '';
        data.forEach(item => {
            if (item.b64_json) {
                const imgContainer = document.createElement('div');
                imgContainer.className = 'image-container';
                const img = document.createElement('img');
                img.src = `data:image/png;base64,${item.b64_json}`;
                img.alt = 'Generated Image';
                imgContainer.appendChild(img);
                imageGrid.appendChild(imgContainer);
            }
        });
    }

    function setLoading(isLoading) {
        generateBtn.disabled = isLoading;
        spinner.classList.toggle('hidden', !isLoading);
        placeholder.classList.toggle('hidden', isLoading || imageGrid.children.length > 0);
        if (isLoading) {
            imageGrid.innerHTML = '';
            hideError();
        }
    }

    function showError(message) {
        errorMessage.textContent = message;
        errorMessage.classList.remove('hidden');
        placeholder.classList.add('hidden');
    }

    function hideError() {
        errorMessage.classList.add('hidden');
    }

    // --- Event Listeners ---
    apiKeyInput.addEventListener('change', loadInitialData);
    imagePreviewContainer.addEventListener('click', () => imageUpload.click());
    imagePreviewContainer.addEventListener('dragover', e => e.preventDefault());
    imagePreviewContainer.addEventListener('drop', e => { e.preventDefault(); handleFile(e.dataTransfer.files[0]); });
    imageUpload.addEventListener('change', e => handleFile(e.target.files[0]));
    clearImageBtn.addEventListener('click', (e) => { e.stopPropagation(); clearImage(); });
    
    widthSlider.addEventListener('input', () => widthValue.textContent = `${widthSlider.value}px`);
    heightSlider.addEventListener('input', () => heightValue.textContent = `${heightSlider.value}px`);
    stepsSlider.addEventListener('input', () => stepsValue.textContent = stepsSlider.value);
    countSlider.addEventListener('input', () => countValue.textContent = countSlider.value);

    generateBtn.addEventListener('click', handleGenerate);

    // --- Initial Load ---
    loadInitialData();
});
