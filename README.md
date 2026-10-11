# Proxmox App: NetBox VM dashboard

This MVP serves a read-only VM inventory from NetBox and links to the existing Jenkins job. The Jenkins link opens the authenticated Jenkins job page; the app does not trigger a build automatically.

## Configure Kubernetes before the first main deployment

The Deployment reads service URLs from a ConfigMap named `proxmox-app-settings`. Create it in the same namespace before merging this version into `main` or running a main-branch deployment:

```sh
kubectl create configmap proxmox-app-settings \
  --from-literal=NETBOX_URL='http://NETBOX_HOST:PORT' \
  --from-literal=JENKINS_JOB_URL='http://JENKINS_HOST:8080/job/proxmox-app/' \
  --namespace default --dry-run=client -o yaml | kubectl apply -f -
```

Replace the placeholders with addresses reachable from the Kubernetes pods. Rerun the command to update the values. The URLs are configuration, not credentials, and are intentionally not committed to this public repository.

Create a NetBox API token for a dedicated account with read-only permission for VM records. Keep the token in a Kubernetes Secret; never put it in GitHub, a Docker image, or browser code. On the Kubernetes administration machine, save only the token to a protected file and create the Secret:

```sh
kubectl create secret generic proxmox-app-config \
  --from-file=netbox-token=/secure/path/netbox-token.txt \
  --namespace default
```

Restrict access to Kubernetes Secrets. NetBox v2 tokens use the `Bearer` authorization scheme configured in the Deployment. For a legacy NetBox token, change `NETBOX_AUTH_SCHEME` to `Token`.

After configuration and deployment, open the app at a Kubernetes node IP on port 30090:

```text
http://KUBERNETES_NODE_IP:30090/
```

## Jenkins: build every branch

The root `Jenkinsfile` is designed for a Jenkins **Multibranch Pipeline**. Jenkins discovers branches that contain this root `Jenkinsfile`:

- Every discovered branch checks out its own code and builds a branch-specific Docker image on the Jenkins agent.
- Only `main` logs in to Docker Hub, publishes the versioned and `latest` image tags, and deploys to Kubernetes.
- Unknown branch metadata fails closed: it may build, but it does not publish or deploy.
- The Docker Hub password is passed through Jenkins Credentials and shell environment variables, not Groovy string interpolation.

Create a separate job after this PR is merged so the existing `proxmox-app` Pipeline can remain available during review. Until the PR is merged, `main` still has the old Jenkinsfile, which publishes and deploys on every run. If you need to scan the new branch before merging, temporarily configure a branch-name filter that excludes `main`; remove that filter after merging.

1. In Jenkins, select **New Item**, enter `proxmox-app-multibranch`, choose **Multibranch Pipeline**, and create it.
2. Under **Branch Sources**, add **GitHub** and select `hearT555/proxmox-app`. The repository is public; use a GitHub credential only if your Jenkins policy requires one.
3. Configure branch discovery to include all branches. Leave the Jenkinsfile path as `Jenkinsfile` at the repository root.
4. Under **Scan Multibranch Pipeline Triggers**, enable **Periodically if not otherwise run** and choose an interval such as **5 minutes**.
5. Save the job and run the initial branch scan. Jenkins creates a child job for each branch that contains a `Jenkinsfile`.

The Jenkins server in this lab uses a private LAN address, so GitHub.com cannot send a webhook directly to it. Periodic scanning is the simplest automatic option without exposing Jenkins. If Jenkins is later made reachable through a secured HTTPS endpoint or a relay, a GitHub webhook can trigger scans sooner.

The current standalone `proxmox-app` job is not automatically converted by creating a Multibranch job. Avoid running both jobs automatically against `main` to prevent duplicate deployments. Once the Multibranch job is verified, disable duplicate triggers on the old job or keep it for manual use only. Existing branches without a root `Jenkinsfile` must receive one before Jenkins can build them.

## Scope and security

- The app only calls the NetBox virtual machines read API. It cannot change NetBox, Proxmox, Kubernetes, or VM state.
- The Jenkins button opens Jenkins so the signed-in user can review the job and click **Build Now** there.
- This MVP uses HTTP and does not add application sign-in. Keep the NodePort on the trusted lab LAN and restrict access at the network/firewall layer; VM inventory may be sensitive.
- Do not add a server-side Jenkins API token until the app has HTTPS and user authentication/authorization. A future automatic trigger should use a Jenkins service account limited to building this one job.

