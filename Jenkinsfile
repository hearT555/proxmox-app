pipeline {
    agent any

    options {
        timestamps()
    }

    environment {
        DOCKER_IMAGE = 'heart2709/proxmox-app'
    }

    triggers {
        pollSCM('H/2 * * * *')
    }

    stages {
        stage('Checkout') {
            steps {
                echo 'Checking out source code...'
                checkout scm
            }
        }

        stage('Validate Files') {
            steps {
                sh '''
                    set -eu
                    test -f app.py
                    test -f index.html
                    test -f Dockerfile
                    test -f deployment.yaml
                    echo "All required files exist."
                '''
            }
        }

        stage('Prepare image tag') {
            steps {
                script {
                    def sourceBranch = env.BRANCH_NAME ?: (env.GIT_BRANCH ?: '')
                    sourceBranch = sourceBranch
                        .replaceFirst(/^refs\\/remotes\\/origin\\//, '')
                        .replaceFirst(/^refs\\/heads\\//, '')
                        .replaceFirst(/^origin\\//, '')

                    def safeBranch = sourceBranch.replaceAll(/[^A-Za-z0-9_.-]/, '-').take(70)
                    if (!safeBranch) {
                        safeBranch = 'unknown'
                    }

                    env.BRANCH_IMAGE = "${env.DOCKER_IMAGE}:${safeBranch}-${env.BUILD_NUMBER}"
                    env.DEPLOY_MAIN = sourceBranch == 'main' ? 'true' : 'false'
                    echo "Building branch '${sourceBranch}' as ${env.BRANCH_IMAGE}"
                    echo "Publish and deploy enabled: ${env.DEPLOY_MAIN}"
                }
            }
        }

        stage('Build Docker image') {
            steps {
                sh 'docker build --pull -t "$BRANCH_IMAGE" .'
            }
        }

        stage('Publish main image') {
            when {
                expression { env.DEPLOY_MAIN == 'true' }
            }
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'dockerhub-credentials',
                    usernameVariable: 'DOCKER_USER',
                    passwordVariable: 'DOCKER_PASS'
                )]) {
                    sh '''
                        set +x
                        set -eu
                        export DOCKER_CONFIG="$(mktemp -d)"
                        trap 'docker logout >/dev/null 2>&1 || true; rm -rf "$DOCKER_CONFIG"' EXIT

                        printf '%s' "$DOCKER_PASS" |
                            docker login -u "$DOCKER_USER" --password-stdin

                        docker push "$BRANCH_IMAGE"
                        docker tag "$BRANCH_IMAGE" "$DOCKER_IMAGE:latest"
                        docker push "$DOCKER_IMAGE:latest"
                    '''
                }
            }
        }

        stage('Deploy main to Kubernetes') {
            when {
                expression { env.DEPLOY_MAIN == 'true' }
            }
            steps {
                sh '''
                    set -eu

                    sed "s#heart2709/proxmox-app:latest#${BRANCH_IMAGE}#g" \
                        deployment.yaml | kubectl apply -f -

                    kubectl rollout status deployment/proxmox-app --timeout=180s
                '''
            }
        }

        stage('Verify Deployment') {
            when {
                expression { env.DEPLOY_MAIN == 'true' }
            }
            steps {
                sh '''
                    set -eu
                    echo "=== Deployment ==="
                    kubectl get deployment proxmox-app
                    echo "=== Pods ==="
                    kubectl get pods -l app=proxmox-app -o wide
                    echo "=== Service ==="
                    kubectl get service proxmox-app-service
                    echo "=== Current image ==="
                    kubectl get deployment proxmox-app \
                        -o jsonpath='{.spec.template.spec.containers[0].image}'
                    echo
                '''
            }
        }
    }

    post {
        success {
            echo 'SUCCESS: Jenkins CI/CD pipeline completed.'
            echo 'Open http://172.16.46.172:30090'
        }

        failure {
            echo 'FAILED: Check Console Output for the failed stage.'
        }
    }
}
