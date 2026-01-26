const uploadModalElement = document.getElementById('upload-modal')
const uploadModal = new Modal(uploadModalElement, {closable: false}, {})

// show modal on click
const uploadShowButton = document.querySelector('button[data-name=show-upload-modal]')
uploadShowButton.addEventListener('click', _ => {
    uploadModal.show()
})

const dragDropSection = document.querySelector('label#dropzone')
dragDropSection.addEventListener('drop', event => {
    event.preventDefault()

    uploadInput.files = event.dataTransfer.files

    uploadInput.dispatchEvent(new Event('change'))
})

dragDropSection.addEventListener('dragover', event => {
    event.preventDefault()
})

const uploadForm = uploadModalElement.querySelector('form')
uploadForm.addEventListener('submit', async (event) => {
    event.preventDefault()

    // get uploaded file
    const formData = new FormData(uploadForm)

    // upload file
    const response = await fetch('/restore', {
        method: 'POST',
        body: formData
    })

    if (!response.ok) {
        // display error message
        createToast('Unable to upload file!', 'error', 10000)

    } else {
        // reset dropzone 
        // change displayed icons
        document.getElementById('upload-icon').classList.remove('hidden')
        document.getElementById('file-icon').classList.add('hidden')

        // change displayed text
        document.getElementById('dropzone-text').classList.remove('hidden')
        document.getElementById('upload-text').classList.add('hidden')

        // reset input
        uploadInput.value = ''

        // hide modal on success
        uploadModal.hide()
    }
})

const uploadInput = document.getElementById('dropzone-file')
uploadInput.addEventListener('change', _ => {
    // change displayed icons
    document.getElementById('upload-icon').classList.add('hidden')
    document.getElementById('file-icon').classList.remove('hidden')

    // change displayed text
    document.getElementById('dropzone-text').classList.add('hidden')
    document.getElementById('upload-text').classList.remove('hidden')

    document.getElementById('uploaded-file-name').textContent = uploadInput.files[0].name
})