
local l = import "lib/frs102.libsonnet";

local config = import "svr-config.jsonnet";

local structure = config.report.structure + {
};

local accts = {
    metadata: {
	"business": {
            "activities": config.metadata.activities,
            "average-employees": [
		config.report.period_average_employees,
		config.report.prev_average_employees,
            ],
            "company-name": config.metadata.company_name,
            "company-number": config.metadata.company_number,
            "entity-scheme": "http://www.companieshouse.gov.uk/",
            "company-formation": {
		"country": config.metadata.country,
		"date": config.metadata.registration_date,
		"form": config.metadata.form,
            },
            "vat-registration": config.metadata.vat_registration,
            "contact": {
		"name": config.metadata.contact_name,
		"address": config.metadata.contact_address,
		"county": config.metadata.contact_county,
		"location": config.metadata.contact_city,
		"postcode": config.metadata.contact_postcode,
		"country": config.metadata.contact_country,
		"email": config.metadata.contact_email,
		"phone": {
                    "area": config.metadata.contact_tel_area,
                    "country": config.metadata.contact_tel_country,
                    "number": config.metadata.contact_tel_number,
                    "type": config.metadata.contact_tel_type,
		}
            },
            "directors": config.metadata.directors,
            "industry-sector": config.metadata.sector,
            "is-dormant": config.metadata.is_dormant,
            "sic-codes": config.metadata.sic_codes,
            "website": {
		"description": config.metadata.web_description,
		"url": config.metadata.web_url,
            },
            "jurisdiction": config.metadata.jurisdiction
	},
	"accounting": {
            "authorised-date": config.report.authorisation_date,
            "balance-sheet-date": config.report.balance_sheet_date,
            "currency": "GBP",
            "decimals": 0,
            "scale": 0,
            "currency-label": "\u00a3",
            "date": config.report.report_date,
            "periods": [
		{
                    "name": config.report.period_name,
                    "start": config.report.period_start_date,
                    "end": config.report.period_end_date,
		},
		{
                    "name": config.report.prev_name,
                    "start": config.report.prev_start_date,
                    "end": config.report.prev_end_date,
		}
            ],
            "signed-by": config.report.director_authorising,
            "signing-officer": "director%d" %
	        config.report.director_authorising_ord,
	}
    },
    accounts:: l.from_element_def(structure, self).with_metadata(self.metadata),
    resource(x):: {
    	"logo": config.report.logo,
	"signature": config.report.signature
    }[x]
};

accts.accounts

