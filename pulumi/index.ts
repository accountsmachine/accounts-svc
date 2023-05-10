
import * as pulumi from "@pulumi/pulumi";
import * as gcp from "@pulumi/gcp";
import { local } from "@pulumi/command";
import * as fs from 'fs';

const imageVersion = process.env.IMAGE_VERSION;

if (!imageVersion)
    throw Error("IMAGE_VERSION not defined");

if (!process.env.ARTIFACT_REPO)
    throw Error("ARTIFACT_REPO not defined");

if (!process.env.ARTIFACT_REPO_REGION)
    throw Error("ARTIFACT_REPO_REGION not defined");

if (!process.env.ARTIFACT_NAME)
    throw Error("ARTIFACT_NAME not defined");

if (!process.env.HOSTNAME)
    throw Error("HOSTNAME not defined");

if (!process.env.GCP_PROJECT)
    throw Error("GCP_PROJECT not defined");

if (!process.env.GCP_REGION)
    throw Error("GCP_REGION not defined");

if (!process.env.ENVIRONMENT)
    throw Error("ENVIRONMENT not defined");

if (!process.env.CLOUD_RUN_REGION)
    throw Error("CLOUD_RUN_REGION not defined");

if (!process.env.DNS_DOMAIN_DESCRIPTION)
    throw Error("DNS_DOMAIN_DESCRIPTION not defined");

if (!process.env.DOMAIN)
    throw Error("DOMAIN not defined");

if (!process.env.MIN_SCALE)
    throw Error("MIN_SCALE not defined");

if (!process.env.MAX_SCALE)
    throw Error("MAX_SCALE not defined");

if (!process.env.CONFIGURATION)
    throw Error("CONFIGURATION not defined");

if (!process.env.BUCKET)
    throw Error("BUCKET not defined");

const provider = new gcp.Provider(
    "gcp",
    {
	project: process.env.GCP_PROJECT,
	region: process.env.GCP_REGION,
    }
);

const enableCloudRun = new gcp.projects.Service(
    "enable-cloud-run",
    {
	service: "run.googleapis.com",
    },
    {
	provider: provider
    }
);

const enableComputeEngine = new gcp.projects.Service(
    "enable-compute-engine",
    {
	service: "compute.googleapis.com",
    },
    {
	provider: provider
    }
);

const enableCloudDns = new gcp.projects.Service(
    "enable-cloud-dns",
    {
	service: "dns.googleapis.com",
    },
    {
	provider: provider
    }
);

const enableArtifactRegistry = new gcp.projects.Service(
    "enable-artifact-registry",
    {
	service: "artifactregistry.googleapis.com",
    },
    {
	provider: provider
    }
);

const enableIAM = new gcp.projects.Service(
    "enable-iam",
    {
	service: "iam.googleapis.com",
    },
    {
	provider: provider
    }
);

const repo = process.env.ARTIFACT_REPO;

const artifactRepo = new gcp.artifactregistry.Repository(
    "artifact-repo",
    {
	description: "repository for " + process.env.ENVIRONMENT,
	format: "DOCKER",
	location: process.env.ARTIFACT_REPO_REGION,
	repositoryId: process.env.ARTIFACT_NAME,
    },
    {
	provider: provider,
	dependsOn: enableArtifactRegistry,
    }
);

const localImageName = "accounts-svc:" + imageVersion;

const imageName = repo + "/accounts-svc:" + imageVersion;

const taggedImage = new local.Command(
    "docker-tag-command",
    {
	create: "docker tag " + localImageName + " " + imageName,
    }
);

const image = new local.Command(
    "docker-push-command",
    {
	create: "docker push " + imageName,
    },
    {
	dependsOn: [taggedImage, artifactRepo],
    }
);

const svcAccount = new gcp.serviceaccount.Account(
    "service-account",
    {
	accountId: "accounts-svc",
	displayName: "Accounts Service",
	description: "Accounts Service",
    },
    {
	provider: provider,
	dependsOn: [enableIAM],
    }
);

const datastoreUserMember = new gcp.projects.IAMMember(
    "datastore-user-role",
    {
	member: svcAccount.email.apply(x => "serviceAccount:" + x),
	project: process.env.GCP_PROJECT,
	role: "roles/datastore.user",
    },
    {
	provider: provider,
	dependsOn: [enableIAM],
    }
);

const firebaseAuthAdminMember = new gcp.projects.IAMMember(
    "firebase-auth-admin-role",
    {
	member: svcAccount.email.apply(x => "serviceAccount:" + x),
	project: process.env.GCP_PROJECT,
	role: "roles/firebaseauth.admin",
    },
    {
	provider: provider,
	dependsOn: [enableIAM],
    }
);

// Stage doesn't have its own storage bucket, no permissions to assign
if (process.env.ENVIRONMENT !== "stage") {

    const bucket = gcp.storage.getBucketOutput(
	{
	    name: process.env.BUCKET,
	},
	{
	    provider: provider,
	}
    );
    
    const bucketAccess = new gcp.storage.BucketIAMMember(
	"bucket-access",
	{
	    bucket: bucket.name,
	    member: svcAccount.email.apply(x => "serviceAccount:" + x),
	    role: "roles/storage.objectAdmin",
	},
	{
	    provider: provider,
	}
    );

}

const svcAccountKey = new gcp.serviceaccount.Key(
    "service-account-key",
    {
	serviceAccountId: svcAccount.name,
    },
    {
	provider: provider,
    }
);

const secret = new gcp.secretmanager.Secret(
    "secret",
    {
	secretId: "accounts-svc-key",
	replication: {
	    automatic: true
	},
    },
    {
	provider: provider,
    }
);

const secretVersion = new gcp.secretmanager.SecretVersion(
    "secret-version",
    {
	secret: secret.id,
	secretData: svcAccountKey.privateKey.apply(x => atob(x)),
    },
    {
	provider: provider,
    }
);

const config = new gcp.secretmanager.Secret(
    "config",
    {
	secretId: "accounts-svc-config",
	replication: {
	    automatic: true
	},
    },
    {
	provider: provider,
    }
);

const configData = process.env.CONFIGURATION;

const configVersion = new gcp.secretmanager.SecretVersion(
    "config-version",
    {
	secret: config.id,
	secretData: configData,
    },
    {
	provider: provider,
    }
);

const keyIamMember = new gcp.secretmanager.SecretIamMember(
    "secret-key-iam-member",
    {
	project: process.env.GCP_PROJECT,
	secretId: secret.id,
	role: "roles/secretmanager.secretAccessor",
	member: svcAccount.email.apply(x => "serviceAccount:" + x),
    },
    {
	provider: provider,
    }
);

const configIamMember = new gcp.secretmanager.SecretIamMember(
    "secret-config-iam-member",
    {
	project: process.env.GCP_PROJECT,
	secretId: config.id,
	role: "roles/secretmanager.secretAccessor",
	member: svcAccount.email.apply(x => "serviceAccount:" + x),
	},
    {
	provider: provider,
    }
);

const service = new gcp.cloudrun.Service(
    "service",
    {
	name: "accounts-svc",
	location: process.env.CLOUD_RUN_REGION,
	template: {
	    metadata: {
		labels: {
		    version: "v" + imageVersion.replace(/\./g, "-"),
		},		
		annotations: {
                    "autoscaling.knative.dev/minScale": process.env.MIN_SCALE,
                    "autoscaling.knative.dev/maxScale": process.env.MAX_SCALE,
		}
	    },
            spec: {
		containerConcurrency: 1000,
		timeoutSeconds: 300,
		serviceAccountName: svcAccount.email,
		containers: [
		    {
			image: imageName,
			ports: [
                            {
				"name": "http1", // Must be http1 or h2c.
				"containerPort": 8080,
                            }
			],
			envs: [
			    // Stops the container from loading
			    // default credentials.  We load credentials
			    // through a secret.
			    {
				name: "NO_GCE_CHECK",
				value: "True",
			    }
			],
			resources: {
                            limits: {
				cpu: "1000m",
				memory: "256Mi",
                            }
			},
			volumeMounts: [
			    {
				name: "accounts-svc-config",
				mountPath: "/configs",
			    },
			    {
				name: "accounts-svc-key",
				mountPath: "/keys",
			    }
			],
		    }
		],
		volumes: [
		    {
			name: "accounts-svc-config",
			secret: {
			    secretName: "accounts-svc-config",
			    items: [
				{
				    key: "latest",
				    path: "accounts-svc-config",
				}
			    ],
			}
		    },
		    {
			name: "accounts-svc-key",
			secret: {
			    secretName: "accounts-svc-key",
			    items: [
				{
				    key: "latest",
				    path: "accounts-svc-key",
				}
			    ],
			}
		    }
		],
            },
	},
    },
    {
	provider: provider,
	dependsOn: [enableCloudRun, image, secretVersion, configVersion],
    }
);

const allUsersPolicy = gcp.organizations.getIAMPolicy(
    {
	bindings: [{
            role: "roles/run.invoker",
            members: ["allUsers"],
	}],
    },
    {
	provider: provider,
    }
);

const noAuthPolicy = new gcp.cloudrun.IamPolicy(
    "no-auth-policy",
    {
	location: service.location,
	project: service.project,
	service: service.name,
	policyData: allUsersPolicy.then(pol => pol.policyData),
    },
    {
	provider: provider,
    }
);

const domainMapping = new gcp.cloudrun.DomainMapping(
    "domain-mapping",
    {
	"name": process.env.HOSTNAME,
	location: process.env.CLOUD_RUN_REGION,
	metadata: {
	    namespace: process.env.GCP_PROJECT,
	},
	spec: {
	    routeName: service.name,
	}
    },
    {
	provider: provider
    }
);

// Get rrdata from domain mapping.
export const host = domainMapping.statuses.apply(
    x => x[0].resourceRecords
).apply(
    x => x ? x[0] : { rrdata: "" }
).apply(
    x => x.rrdata
);

const zone = new gcp.dns.ManagedZone(
    "zone",
    {
	name: process.env.DNS_DOMAIN_DESCRIPTION,
	description: process.env.DOMAIN,
	dnsName: process.env.DOMAIN,
	labels: {
	},
    },
    {
	provider: provider,
	dependsOn: [enableCloudDns],
    }
);

const recordSet = new gcp.dns.RecordSet(
    "resource-record",
    {
	name: process.env.HOSTNAME + ".",
	managedZone: zone.name,
	type: "CNAME",
	ttl: 300,
	rrdatas: [host],
    },
    {
	provider: provider,
	dependsOn: zone,
    }
);

const serviceMon = new gcp.monitoring.GenericService(
    "service-monitoring",
    {
	basicService: {
            serviceLabels: {
		service_name: service.name,
		location: process.env.CLOUD_RUN_REGION,
            },
            serviceType: "CLOUD_RUN",
	},
	displayName: "API service (" + process.env.ENVIRONMENT + ")",
	serviceId: "api-service-" + process.env.ENVIRONMENT + "-mon",
	userLabels: {
	    "service": service.name,
	    "application": "accounts-svc",
	    "environment": process.env.ENVIRONMENT,
	},
    },
    {
	provider: provider,
    }
);

const latencySlo = new gcp.monitoring.Slo(
    "latency-slo",
    {
	service: serviceMon.serviceId,
	sloId: "api-service-" + process.env.ENVIRONMENT + "-latency-slo",
	displayName: "API latency (" + process.env.ENVIRONMENT + ")",
	goal: 0.95,
	rollingPeriodDays: 5,
	basicSli: {
	    latency: {
		threshold: "2s"
	    }
	},
    },
    {
	provider: provider,
    }
);

const availabilitySlo = new gcp.monitoring.Slo(
    "availability-slo",
    {
	service: serviceMon.serviceId,
	sloId: "api-service-" + process.env.ENVIRONMENT + "-availability-slo",
	displayName: "API availability (" + process.env.ENVIRONMENT + ")",
	goal: 0.95,
	rollingPeriodDays: 5,
	windowsBasedSli: {
	    windowPeriod: "3600s",
	    goodTotalRatioThreshold: {
		basicSliPerformance: {
		    availability: {
		    }
		},
		threshold: 0.9,
	    }
	}
    },
    {
	provider: provider,
    }
);

// Stage uses data stored on production, so on prod deploy, need to grant access
// to stage's user service user.  This assumes that staging is already deployed.

if (process.env.ENVIRONMENT === "prod") {

    const stagingUser =
	  "serviceAccount:" +
	  "accounts-svc@accounts-machine-stage.iam.gserviceaccount.com";
 
    const datastoreStagingMember = new gcp.projects.IAMMember(
	"datastore-staging-role",
	{
	    member: stagingUser,
	    project: process.env.GCP_PROJECT,
	    role: "roles/datastore.user",
	},
	{
	    provider: provider,
	    dependsOn: [enableIAM],
	}
    );

    const firebaseAuthStagingMember = new gcp.projects.IAMMember(
	"firebase-auth-staging-role",
	{
	    member: stagingUser,
	    project: process.env.GCP_PROJECT,
	    role: "roles/firebaseauth.admin",
	},
	{
	    provider: provider,
	    dependsOn: [enableIAM],
	}
    );

    const bucket = gcp.storage.getBucketOutput(
	{
	    name: process.env.BUCKET,
	},
	{
	    provider: provider,
	}
    );
    
    const stagingBucketAccess = new gcp.storage.BucketIAMMember(
	"staging-bucket-access",
	{
	    bucket: bucket.name,
	    member: stagingUser,
	    role: "roles/storage.objectAdmin",
	},
	{
	    provider: provider,
	}
    );

}

