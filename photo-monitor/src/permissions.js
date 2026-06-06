export function uniqueStrings(values) {
  return Array.from(new Set(values.map((item) => (item || "").trim()).filter(Boolean)))
}

export function parseMatrixPermission(permission) {
  if (typeof permission !== "string" || !permission.startsWith("perm:")) {
    return null
  }
  const parts = permission.slice(5).split(":")
  if (parts.length !== 3 || parts.some((item) => !item)) {
    return null
  }
  return { system: parts[0], department: parts[1], action: parts[2] }
}

export function hasMatrixPermission(user, system, action, department = "") {
  if (!user) {
    return false
  }
  if (user.role === "admin") {
    return true
  }
  const targetDepartment = department || "*"
  return (user.permissions ?? []).some((permission) => {
    const parsed = parseMatrixPermission(permission)
    if (!parsed || parsed.system !== system || parsed.action !== action) {
      return false
    }
    return parsed.department === "*" || parsed.department === targetDepartment
  })
}

export function hasAnyMatrixAction(user, system, actions) {
  if (!user) {
    return false
  }
  if (user.role === "admin") {
    return true
  }
  return (user.permissions ?? []).some((permission) => {
    const parsed = parseMatrixPermission(permission)
    return parsed && parsed.system === system && actions.includes(parsed.action)
  })
}

export function getMatrixDepartments(user, system, action) {
  if (!user) {
    return []
  }
  if (user.role === "admin") {
    return []
  }
  const departments = []
  for (const permission of user.permissions ?? []) {
    const parsed = parseMatrixPermission(permission)
    if (!parsed) {
      continue
    }
    if (system && parsed.system !== system) {
      continue
    }
    if (action && parsed.action !== action) {
      continue
    }
    departments.push(parsed.department)
  }
  if (departments.includes("*")) {
    return []
  }
  return uniqueStrings(departments)
}

export function isSameOrChildDepartment(department, parent) {
  const normalizedDepartment = (department || "").trim()
  const normalizedParent = (parent || "").trim()
  return (
    Boolean(normalizedDepartment && normalizedParent) &&
    (normalizedDepartment === normalizedParent || normalizedDepartment.startsWith(`${normalizedParent}/`))
  )
}

export function getStructureVisibleDepartments(user, departments) {
  const normalizedDepartments = uniqueStrings(departments)
  if (!user) {
    return []
  }
  if (user.role === "admin") {
    return normalizedDepartments
  }

  const allowedDepartments = getMatrixDepartments(user, "structure", "read")
  const scopedDepartments = allowedDepartments.length ? allowedDepartments : uniqueStrings([user.department])
  return normalizedDepartments.filter((department) =>
    scopedDepartments.some((allowed) => isSameOrChildDepartment(department, allowed)),
  )
}

export function getDepartmentViewOptions(user, departments, system = null, action = "read") {
  if (!user) {
    return []
  }

  if (user.role === "admin") {
    return uniqueStrings(departments)
  }

  const matrixDepartments = getMatrixDepartments(user, system, action)
  const departmentOptions = matrixDepartments.length
    ? matrixDepartments
    : uniqueStrings([...(departments ?? []), ...(user.department_permissions ?? []), user.department ?? ""])

  return departmentOptions.length > 1 ? ["", ...departmentOptions] : departmentOptions
}

export function hasMatrixReadPermission(user, system) {
  return hasAnyMatrixAction(user, system, ["read"])
}

export function hasCameraPermission(user) {
  return hasMatrixReadPermission(user, "photos")
}

export function hasModuleAccess(user, module) {
  const actions = module.key === "structure" ? ["read"] : ["read", "create", "update", "delete"]
  return hasAnyMatrixAction(user, module.matrixSystem, actions)
}

