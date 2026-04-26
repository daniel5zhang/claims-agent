import request from './request'

export function generateExcel(schemeId) {
  return request.post('/excel/generate', { scheme_id: schemeId })
}

export function getExcel(excelId) {
  return request.get(`/excel/${excelId}`)
}

export function downloadExcel(excelId) {
  window.open(`/api/excel/${excelId}/download`, '_blank')
}
