variable "version" {
    type = string
    default = "3.11.7"
}
variable "docker_repo" {
    type = string
    default = "ghcr.io/datawhores/of-scraper"
}
variable "version_parts" {
    default = split(".", version)
}
variable "major_version" {
    default = version_parts[0]
}

variable "minor_version" {
    default = version_parts[1]
}

variable "patch_version" {
    default = version_parts[2]
}


group "default" {
    targets = ["alpine", "debian"]
}
target "debian" {
    matrix = {
        size = ["full", "minimal"]
    }
    name = "${size}"
    dockerfile = "Dockerfile"
    context = "."
    args = {
        SIZE = size
        }
    platforms = ["linux/amd64", "linux/arm64"]
    tags = [
        "${docker_repo}:${major_version}.${minor_version}.${patch_version}-${size}",
        "${docker_repo}:${major_version}.${minor_version}-${size}",
        "${docker_repo}:${major_version}-${size}",
        "${docker_repo}:${size}",
        "${size == "minimal" ? "${docker_repo}:${major_version}.${minor_version}.${patch_version}" : ""}",
        "${size == "minimal" ? "${docker_repo}:${major_version}.${minor_version}" : ""}",
        "${size == "minimal" ? "${docker_repo}:${major_version}" : ""}",
        "${size == "minimal" ? "${docker_repo}:latest" : ""}"
    ]
    cache-from=[ "type=gha" ]
    cache-to=[ "type=gha,mode=max" ]
}

target "alpine" {
    matrix = {
        python_version = ["3.12", "3.11"]
        size = ["full", "minimal"]
    }
    name = replace("python-${python_version}-alpine-${size}", ".", "-")
    dockerfile = "Dockerfile.alpine"
    args = {
        PYTHON_VERSION = python_version,
        SIZE = size
        }
    platforms = ["linux/amd64", "linux/arm64"]
    context = "."
    tags = [
        "${docker_repo}:${major_version}.${minor_version}.${patch_version}-python-${python_version}-alpine-${size}",
        "${docker_repo}:${major_version}.${minor_version}-python-${python_version}-alpine-${size}",
        "${docker_repo}:${major_version}-python-${python_version}-alpine-${size}",
        "${docker_repo}:python-${python_version}-alpine-${size}",
        "${size == "minimal" ? "${docker_repo}:alpine" : ""}"
    ]
    cache-from=[ "type=gha" ]
    cache-to=[ "type=gha,mode=max" ]
}