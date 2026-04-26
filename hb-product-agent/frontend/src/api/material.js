import request from './request'

export function listServices(params = {}) {
  return request.get('/material/services', { params })
}

export function getService(serviceId) {
  return request.get(`/material/services/${serviceId}`)
}

export function listCategories() {
  return request.get('/material/categories')
}
