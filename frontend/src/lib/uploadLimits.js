// Topes de una subida. Son el ESPEJO de `Config.MAX_UPLOAD_FILES` y `Config.MAX_UPLOAD_IMAGES` del servidor: sirven para
// avisar al añadir un archivo y no al lanzar el análisis (donde el servidor lo rechazaba y la persona solo veía
// «el análisis ha fallado»). El servidor sigue mandando: si su tope fuera otro, su mensaje se muestra tal cual.
export const MAX_UPLOAD_FILES = 10
export const MAX_UPLOAD_IMAGES = 8
export const IMAGE_EXTENSIONS = ['png', 'jpg', 'jpeg', 'webp', 'gif']

export const extensionOf = (name) => String(name || '').split('.').pop().toLowerCase()
export const isImageFile = (file) => IMAGE_EXTENSIONS.includes(extensionOf(file && file.name))

/**
 * Reparte `incoming` entre lo que cabe y lo que sobra, dado lo ya añadido (`current`).
 * Devuelve { accepted, overFiles, overImages }: cuántos se dejaron fuera por cada tope.
 */
export function fitUploads(current, incoming, maxFiles = MAX_UPLOAD_FILES, maxImages = MAX_UPLOAD_IMAGES) {
  let files = current.length
  let images = current.filter(isImageFile).length
  const accepted = []
  let overFiles = 0
  let overImages = 0
  for (const file of incoming) {
    if (files >= maxFiles) { overFiles++; continue }
    if (isImageFile(file) && images >= maxImages) { overImages++; continue }
    accepted.push(file)
    files++
    if (isImageFile(file)) images++
  }
  return { accepted, overFiles, overImages }
}
