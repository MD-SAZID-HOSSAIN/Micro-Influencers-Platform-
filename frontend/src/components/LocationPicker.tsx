import { FormField, Select } from './ui';
import { COUNTRY_NAMES, citiesOf } from '../lib/places';

/**
 * Country and city as two dropdowns: pick the country, then a city from that country's list.
 * It renders two form fields, so the parent decides the layout (put it inside a grid).
 *
 * A value saved earlier that is not in the lists (typed by hand before this picker existed) is kept as an
 * extra choice, so it is shown and never silently dropped. Picking another country clears the city.
 */
export function LocationPicker({
  country,
  city,
  onChange,
}: {
  country: string;
  city: string;
  onChange: (next: { country: string; city: string }) => void;
}) {
  const cities = citiesOf(country);
  const countryOptions = country && !COUNTRY_NAMES.includes(country) ? [...COUNTRY_NAMES, country] : COUNTRY_NAMES;
  const cityOptions = city && !cities.includes(city) ? [...cities, city] : cities;

  return (
    <>
      <FormField label="Country" htmlFor="country" required>
        <Select id="country" value={country} onChange={(e) => onChange({ country: e.target.value, city: '' })}>
          <option value="">Select country</option>
          {countryOptions.map((c) => <option key={c} value={c}>{c}</option>)}
        </Select>
      </FormField>

      <FormField label="City" htmlFor="city" required>
        <Select
          id="city"
          value={city}
          disabled={!country}
          onChange={(e) => onChange({ country, city: e.target.value })}
        >
          <option value="">{country ? 'Select city' : 'Select a country first'}</option>
          {cityOptions.map((c) => <option key={c} value={c}>{c}</option>)}
        </Select>
      </FormField>
    </>
  );
}
