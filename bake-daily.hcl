variable "GITHUB_SHA" {
    type = string
    default = "latest"
}

variable "REGISTRY" {
    type = string
    default = "ghcr.io/datawhores/of-scraper"
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
        "${target.docker-metadata-action.args.DOCKER_META_IMAGES}:nightly-${size}-${GITHUB_SHA}",
        "${target.docker-metadata-action.args.DOCKER_META_IMAGES}:nightly-${size}",
        "${size == "minimal" ? "${target.docker-metadata-action.args.DOCKER_META_IMAGES}:nightly" : ""}"
    ]
    cache-from=[ "type=gha" ]
    cache-to=[ "type=gha,mode=max" ]
    labels = target.docker-metadata-action.labels
    annotations = target.docker-metadata-action.annotations
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
        "${target.docker-metadata-action.args.DOCKER_META_IMAGES}:nightly-python-${python_version}-alpine-${size}-${GITHUB_SHA}",
        "${target.docker-metadata-action.args.DOCKER_META_IMAGES}:nightly-python-${python_version}-alpine-${size}",
        "${size == "minimal" ? "${target.docker-metadata-action.args.DOCKER_META_IMAGES}:nightly-alpine" : ""}"
    ]
    cache-from=[ "type=gha" ]
    cache-to=[ "type=gha,mode=max" ]
    labels = target.docker-metadata-action.labels
    annotations = target.docker-metadata-action.annotations
}