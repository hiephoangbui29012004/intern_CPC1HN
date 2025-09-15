def setupVersions() {
  def versionSources = [
    "grep '^__version__' src/__init__.py | sed 's/__version__ = \"\\(.*\\)\"/\\1/' 2>/dev/null || echo ''",
    "echo '1.0.0'"
  ]
  
  env.APP_VERSION = ""
  for (source in versionSources) {
    def version = sh(script: source, returnStdout: true).trim()
    if (version && version != "") {
      env.APP_VERSION = version
      echo "Found version ${env.APP_VERSION} using: ${source.split('||')[0].trim()}"
      break
    }
  }
  
  if (!env.APP_VERSION || env.APP_VERSION == "") {
    env.APP_VERSION = "1.0.0"
    echo "No version found, using default: ${env.APP_VERSION}"
  }

  // Get git commit hash
  env.GIT_COMMIT_SHORT = sh(script: 'git rev-parse --short HEAD', returnStdout: true).trim()

  // Get git tag if available
  env.GIT_TAG = sh(script: "git describe --tags --abbrev=0 || echo ''", returnStdout: true).trim()

  // Use git tag if available, otherwise use commit hash
  env.DOCKER_VERSION_TAG = env.GIT_TAG ? env.GIT_TAG : "${env.APP_VERSION}-${env.GIT_COMMIT_SHORT}"

  echo "Building version: ${env.DOCKER_VERSION_TAG}"
}

def buildDockerImage(){
  sh "echo Building Docker image with version: ${env.DOCKER_VERSION_TAG}"

  if(env.DEPLOY_ENV != 'test'){
    sh """
      docker build --build-arg VERSION=${env.DOCKER_VERSION_TAG} \
        -t ${DOCKER_NAMESPACE}/${APP_NAME}:${env.DOCKER_VERSION_TAG} \
        -t ${DOCKER_NAMESPACE}/${APP_NAME}:latest .
    """
  } else{
    sh """
      docker build --build-arg VERSION=${env.DOCKER_VERSION_TAG} \
        -t ${DOCKER_NAMESPACE}/${APP_NAME}:${env.DOCKER_VERSION_TAG} .
    """
  }
}

def pushDockerImage(String versionTag) {
    sh "echo Pushing Docker images to ${env.DOCKER_REGISTRY}"
    sh "echo ${env.DOCKER_CREDS_PSW} | docker login ${env.DOCKER_REGISTRY} -u ${env.DOCKER_CREDS_USR} --password-stdin"
    sh "docker push ${env.DOCKER_NAMESPACE}/${env.APP_NAME}:${versionTag}"
    if(env.DEPLOY_ENV != 'test'){
      sh "docker push ${env.DOCKER_NAMESPACE}/${env.APP_NAME}:latest"
    }            
    sh "docker logout ${env.DOCKER_REGISTRY}"
}

return this
