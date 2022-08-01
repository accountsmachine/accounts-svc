
local l = import "lib/uk-corptax.libsonnet";

local config = import "svr-config.jsonnet";

local structure = config.report.structure + {
};

local accts = {
    metadata: {
	"business": {
            "company-name": config.metadata.company_name,
            "company-number": config.metadata.company_number,
            "entity-scheme": "http://www.companieshouse.gov.uk/",
	},
	"accounting": {
            "date": config.report.today,
            "currency": "GBP",
            "decimals": 0,
            "scale": 0,
            "currency-label": "\u00a3",
            "periods": [
		{
                    "name": config.report.period_name,
                    "start": config.report.period_start_date,
                    "end": config.report.period_end_date,
		}
	    ]
	},
   "tax": {
       "utr": config.metadata.utr,
        "period": {
            "name": config.report.period_name,
            "start": config.report.period_start_date,
            "end": config.report.period_end_date,
        },
        "fy1": {
	    "name": config.report.fy1.name,
	    "year": config.report.fy1.name,
            "start": config.report.fy1.start,
            "end": config.report.fy1.end
        },
       "fy2": {
	    "name": config.report.fy2.name,
	    "year": config.report.fy2.name,
            "start": config.report.fy2.start,
            "end": config.report.fy2.end
        }
   }
    },
    accounts:: l.from_element_def(structure, self)
	.with_metadata(self.metadata),
    resource(x):: {
    	"default-logo": import "detail/logo.jsonnet",
    	"logo": import "detail/logo.jsonnet",
	"cyberapocalypse-logo": import "detail/cyberapocalypse-logo.jsonnet",
	"signature": import "detail/signature.jsonnet"
    }[x]
};

accts.accounts

