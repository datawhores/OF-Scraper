variable "GITHUB_SHA" {
    type = string
    default = "latest"
}

variable "REGISTRY" {
    type = string
    default = "ghcr.io/datawhores/of-scraper"
}

group "default" {
    targets = ["alpine", "ubuntu"]
}
target "ubuntu" {
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
        "${REGISTRY}:nightly-${size}-${GITHUB_SHA}",
        "${REGISTRY}:nightly-${size}",
        "${size == "minimal" ? "${REGISTRY}:nightly" : ""}"
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
        "${REGISTRY}:nightly-python-${python_version}-alpine-${size}-${GITHUB_SHA}",
        "${REGISTRY}:nightly-python-${python_version}-alpine-${size}",
        "${size == "minimal" ? "${REGISTRY}:nightly-alpine" : ""}"
    ]
    cache-from=[ "type=gha" ]
    cache-to=[ "type=gha,mode=max" ]
}