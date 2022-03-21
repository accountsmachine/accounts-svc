
local l = import "lib/uk-vat.libsonnet";

local config = import "svr-config.jsonnet";

local resources = import "resources.jsonnet";

local structure = config.report.structure + {
    "element": "vat",
    "elements": config.report.structure.elements
};

//local structure = {
//    "accounts_file": "accounts.dat",
//    "accounts_kind": "piecash",
//};

local accts = {
    metadata: {
        "business": {
    	    "company-name": config.metadata.company_name,
            "company-number": config.metadata.company_number,
            "entity-scheme": "http://www.companieshouse.gov.uk/",
            "vat-registration": config.metadata.vat_registration
	},
	"accounting": {
            "currency": "GBP",
            "decimals": 2,
            "scale": 0,
            "currency-label": "\u00a3",
            "date": config.report.today,
            "periods": [
		{
                    "name": "VAT",
                    "start": config.report.start,
                    "end": config.report.end
		}
            ]
	}
    },
    accounts:: l.element(structure, self)
	.with_metadata(self.metadata),
    resource(x):: {
    	"default-logo": import "detail/logo.jsonnet",
	"cyberapocalypse-logo": import "detail/cyberapocalypse-logo.jsonnet",
	"signature": import "detail/signature.jsonnet"
    }[x]
};

accts.accounts

