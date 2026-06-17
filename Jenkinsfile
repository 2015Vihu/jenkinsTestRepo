pipeline {

    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '10'))
    }

    environment {
        FLUTTER_HOME = '/Users/Alok/Desktop/Flutter/flutter'
        JAVA_HOME = '/Library/Java/JavaVirtualMachines/jdk-17.jdk/Contents/Home'
        ANDROID_HOME = '/Users/Alok/Library/Android/sdk'
        ANDROID_SDK_ROOT = '/Users/Alok/Library/Android/sdk'
        NODE20_BIN = '/opt/homebrew/bin'
        PYTHON_BIN = 'python3'

        OLLAMA_BASE_URL = 'http://127.0.0.1:11434'
        OLLAMA_MODEL = 'qwen2.5-coder:7b'
        GITHUB_API_URL = 'https://api.github.com'

        AI_REVIEW_RETRIES = '3'
        AI_REVIEW_MAX_DIFF_BYTES = '180000'
        AI_REVIEW_MAX_FILES = '25'

        TESTER_EMAIL = 'learningforfuture72@example.com'
        PATH = "${FLUTTER_HOME}/bin:${ANDROID_HOME}/platform-tools:${ANDROID_HOME}/cmdline-tools/latest/bin:${JAVA_HOME}/bin:${NODE20_BIN}:${env.PATH}"
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('PR Information') {
            steps {
                script {
                    echo '================================='
                    echo "BRANCH_NAME   = ${env.BRANCH_NAME}"
                    echo "CHANGE_ID     = ${env.CHANGE_ID}"
                    echo "CHANGE_BRANCH = ${env.CHANGE_BRANCH}"
                    echo "CHANGE_TARGET = ${env.CHANGE_TARGET}"
                    echo "CHANGE_AUTHOR = ${env.CHANGE_AUTHOR}"
                    echo "CHANGE_TITLE  = ${env.CHANGE_TITLE}"
                    echo "CHANGE_URL    = ${env.CHANGE_URL}"
                    echo '================================='
                }
            }
        }

        stage('Resolve Repository Metadata') {
            steps {
                script {
                    def remoteUrl = sh(script: 'git config --get remote.origin.url', returnStdout: true).trim()
                    env.GITHUB_REPOSITORY = remoteUrl
                        .replaceFirst(/^git@github.com:/, '')
                        .replaceFirst(/^https:\/\/github.com\//, '')
                        .replaceFirst(/\.git$/, '')

                    if (!env.GITHUB_REPOSITORY?.trim()) {
                        error('Unable to resolve GitHub repository from remote.origin.url')
                    }

                    echo "GITHUB_REPOSITORY = ${env.GITHUB_REPOSITORY}"
                }
            }
        }

        stage('Debug Environment') {
            steps {
                sh '''
                    echo "=============================="
                    echo "PATH=$PATH"
                    echo "=============================="

                    which flutter || true
                    flutter --version || true

                    which java || true
                    java -version || true

                    which python3 || true
                    python3 --version || true

                    which git || true
                    git --version || true
                '''
            }
        }

        stage('Verify Project') {
            steps {
                sh '''
                    test -f pubspec.yaml
                    test -f ci/ai_review.py
                    test -f ci/prompts/qwen_pr_review_prompt.txt
                    flutter --version
                '''
            }
        }

        stage('Flutter Clean') {
            steps {
                sh 'flutter clean'
            }
        }

        stage('Flutter Pub Get') {
            steps {
                sh 'flutter pub get'
            }
        }

        stage('Flutter Analyze') {
            steps {
                sh '''
                    set +e
                    flutter analyze > analyze_output.txt 2>&1
                    status=$?
                    set -e

                    echo "========== flutter analyze output =========="
                    cat analyze_output.txt
                    echo "==========================================="

                    exit $status
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'analyze_output.txt', allowEmptyArchive: true
                }
            }
        }

        stage('Flutter Test') {
            steps {
                sh '''
                    set +e
                    flutter test > test_output.txt 2>&1
                    status=$?
                    set -e

                    echo "=========== flutter test output ==========="
                    cat test_output.txt
                    echo "==========================================="

                    exit $status
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'test_output.txt', allowEmptyArchive: true
                }
            }
        }

        stage('Expert Review (Qwen via Ollama)') {
            when {
                expression { env.CHANGE_ID?.trim() }
            }
            options {
                timeout(time: 15, unit: 'MINUTES')
            }
            steps {
                withCredentials([
                    string(credentialsId: 'github-pat', variable: 'GITHUB_TOKEN')
                ]) {
                    retry(2) {
                        sh '''
                            set -eu

                            mkdir -p build/ai-review

                            echo "Checking Ollama availability at $OLLAMA_BASE_URL"
                            curl -fsS "$OLLAMA_BASE_URL/api/tags" > build/ai-review/ollama_tags.json

                            git fetch --no-tags origin "+refs/heads/${CHANGE_TARGET}:refs/remotes/origin/${CHANGE_TARGET}"

                            "$PYTHON_BIN" ci/ai_review.py \
                              --repo "$GITHUB_REPOSITORY" \
                              --pr-number "$CHANGE_ID" \
                              --pr-title "${CHANGE_TITLE:-}" \
                              --pr-author "${CHANGE_AUTHOR:-}" \
                              --pr-url "${CHANGE_URL:-}" \
                              --base-ref "origin/${CHANGE_TARGET}" \
                              --head-ref "${CHANGE_BRANCH:-$BRANCH_NAME}" \
                              --head-sha "$GIT_COMMIT" \
                              --ollama-url "$OLLAMA_BASE_URL" \
                              --ollama-model "$OLLAMA_MODEL" \
                              --github-token "$GITHUB_TOKEN" \
                              --github-api-url "$GITHUB_API_URL" \
                              --prompt-file ci/prompts/qwen_pr_review_prompt.txt \
                              --analysis-file analyze_output.txt \
                              --test-file test_output.txt \
                              --output-dir build/ai-review \
                              --max-diff-bytes "$AI_REVIEW_MAX_DIFF_BYTES" \
                              --max-files "$AI_REVIEW_MAX_FILES" \
                              --retries "$AI_REVIEW_RETRIES"
                        '''
                    }
                }
            }
            post {
                always {
                    archiveArtifacts artifacts: 'build/ai-review/**/*', allowEmptyArchive: true
                }
            }
        }

        stage('Prepare Android Signing') {
            when {
                expression { !env.CHANGE_ID?.trim() }
            }
            steps {
                withCredentials([
                    file(credentialsId: 'android-upload-keystore', variable: 'ANDROID_KEYSTORE_FILE'),
                    string(credentialsId: 'android-store-password', variable: 'ANDROID_STORE_PASSWORD'),
                    string(credentialsId: 'android-key-password', variable: 'ANDROID_KEY_PASSWORD'),
                    string(credentialsId: 'android-key-alias', variable: 'ANDROID_KEY_ALIAS')
                ]) {
                    sh '''
                        set -eu

                        cp "$ANDROID_KEYSTORE_FILE" android/app/upload-keystore.jks

                        cat > android/key.properties <<EOF
storePassword=$ANDROID_STORE_PASSWORD
keyPassword=$ANDROID_KEY_PASSWORD
keyAlias=$ANDROID_KEY_ALIAS
storeFile=../app/upload-keystore.jks
EOF
                    '''
                }
            }
        }

        stage('Build Signed Release APK') {
            when {
                expression { !env.CHANGE_ID?.trim() }
            }
            steps {
                sh 'flutter build apk --release'
            }
        }

        stage('Build Signed Release AAB') {
            when {
                expression { !env.CHANGE_ID?.trim() }
            }
            steps {
                sh 'flutter build appbundle --release'
            }
        }

        stage('Show Build Outputs') {
            when {
                expression { !env.CHANGE_ID?.trim() }
            }
            steps {
                sh '''
                    echo "APK outputs:"
                    ls -lh build/app/outputs/flutter-apk || true

                    echo "AAB outputs:"
                    ls -lh build/app/outputs/bundle/release || true
                '''
            }
        }

        stage('Archive Artifacts') {
            when {
                expression { !env.CHANGE_ID?.trim() }
            }
            steps {
                archiveArtifacts artifacts: '''
                    build/app/outputs/flutter-apk/*.apk,
                    build/app/outputs/bundle/release/*.aab
                ''', fingerprint: true
            }
        }

        stage('Check Firebase CLI') {
            when {
                expression { !env.CHANGE_ID?.trim() }
            }
            steps {
                sh '''
                    export PATH="$NODE20_BIN:$PATH"

                    which node
                    node -v

                    which firebase
                    firebase --version
                '''
            }
        }

        stage('Upload APK to Firebase App Distribution') {
            when {
                expression { !env.CHANGE_ID?.trim() }
            }
            steps {
                withCredentials([
                    file(credentialsId: 'firebase-service-account', variable: 'GOOGLE_APPLICATION_CREDENTIALS'),
                    string(credentialsId: 'firebase-android-app-id', variable: 'FIREBASE_ANDROID_APP_ID')
                ]) {
                    sh '''
                        export PATH="$NODE20_BIN:$PATH"

                        firebase appdistribution:distribute build/app/outputs/flutter-apk/app-release.apk \
                          --app "$FIREBASE_ANDROID_APP_ID" \
                          --release-notes "Jenkins build #${BUILD_NUMBER} from commit ${GIT_COMMIT}" \
                          --testers "$TESTER_EMAIL"
                    '''
                }
            }
        }
    }

    post {

        success {
            echo 'Flutter CI pipeline completed successfully.'
        }

        failure {
            echo 'Flutter CI pipeline failed.'
        }

        always {
            sh '''
                rm -f android/key.properties
                rm -f android/app/upload-keystore.jks
            '''
        }
    }
}
