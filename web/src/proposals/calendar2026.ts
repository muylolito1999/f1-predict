export interface CalendarRace {
  round: number;
  country: string;
  countryCode: string;
  flag: string;
  name: string;       // Grand Prix display name
  circuit: string;    // Official circuit name
  city: string;       // Sakhir, Jeddah, Melbourne...
  date: string;       // ISO date of race day
  laps: number;
  length: number;     // km
  status?: "past" | "upcoming" | "next";
}

/** 2026 calendar — hand-compiled from the published schedule. */
export const CALENDAR_2026: CalendarRace[] = [
  { round: 1,  country: "Bahrain",     countryCode: "BHR", flag: "🇧🇭", name: "Bahrain Grand Prix",           circuit: "Bahrain International Circuit", city: "Sakhir",            date: "2026-03-08", laps: 57, length: 5.412 },
  { round: 2,  country: "Saudi Arabia",countryCode: "SAU", flag: "🇸🇦", name: "Saudi Arabian Grand Prix",     circuit: "Jeddah Corniche Circuit",       city: "Jeddah",            date: "2026-03-15", laps: 50, length: 6.174 },
  { round: 3,  country: "Australia",   countryCode: "AUS", flag: "🇦🇺", name: "Australian Grand Prix",        circuit: "Albert Park Circuit",           city: "Melbourne",         date: "2026-03-29", laps: 58, length: 5.278 },
  { round: 4,  country: "Japan",       countryCode: "JPN", flag: "🇯🇵", name: "Japanese Grand Prix",          circuit: "Suzuka International",          city: "Suzuka",            date: "2026-04-12", laps: 53, length: 5.807 },
  { round: 5,  country: "China",       countryCode: "CHN", flag: "🇨🇳", name: "Chinese Grand Prix",           circuit: "Shanghai International",        city: "Shanghai",          date: "2026-04-19", laps: 56, length: 5.451 },
  { round: 6,  country: "USA",         countryCode: "USA", flag: "🇺🇸", name: "Miami Grand Prix",             circuit: "Miami International",           city: "Miami",             date: "2026-05-03", laps: 57, length: 5.412 },
  { round: 7,  country: "Canada",      countryCode: "CAN", flag: "🇨🇦", name: "Canadian Grand Prix",          circuit: "Circuit Gilles Villeneuve",     city: "Montréal",          date: "2026-05-24", laps: 70, length: 4.361 },
  { round: 8,  country: "Monaco",      countryCode: "MON", flag: "🇲🇨", name: "Monaco Grand Prix",            circuit: "Circuit de Monaco",             city: "Monte Carlo",       date: "2026-06-07", laps: 78, length: 3.337 },
  { round: 9,  country: "Spain",       countryCode: "ESP", flag: "🇪🇸", name: "Spanish Grand Prix",           circuit: "Circuit de Barcelona-Catalunya",city: "Barcelona",         date: "2026-06-14", laps: 66, length: 4.657 },
  { round: 10, country: "Austria",     countryCode: "AUT", flag: "🇦🇹", name: "Austrian Grand Prix",          circuit: "Red Bull Ring",                 city: "Spielberg",         date: "2026-06-28", laps: 71, length: 4.318 },
  { round: 11, country: "UK",          countryCode: "GBR", flag: "🇬🇧", name: "British Grand Prix",           circuit: "Silverstone Circuit",           city: "Silverstone",       date: "2026-07-05", laps: 52, length: 5.891 },
  { round: 12, country: "Belgium",     countryCode: "BEL", flag: "🇧🇪", name: "Belgian Grand Prix",           circuit: "Spa-Francorchamps",             city: "Spa",               date: "2026-07-26", laps: 44, length: 7.004 },
  { round: 13, country: "Hungary",     countryCode: "HUN", flag: "🇭🇺", name: "Hungarian Grand Prix",         circuit: "Hungaroring",                   city: "Budapest",          date: "2026-08-02", laps: 70, length: 4.381 },
  { round: 14, country: "Netherlands", countryCode: "NED", flag: "🇳🇱", name: "Dutch Grand Prix",             circuit: "Circuit Zandvoort",             city: "Zandvoort",         date: "2026-08-23", laps: 72, length: 4.259 },
  { round: 15, country: "Italy",       countryCode: "ITA", flag: "🇮🇹", name: "Italian Grand Prix",           circuit: "Monza Circuit",                 city: "Monza",             date: "2026-09-06", laps: 53, length: 5.793 },
  { round: 16, country: "Azerbaijan",  countryCode: "AZE", flag: "🇦🇿", name: "Azerbaijan Grand Prix",        circuit: "Baku City Circuit",             city: "Baku",              date: "2026-09-20", laps: 51, length: 6.003 },
  { round: 17, country: "Singapore",   countryCode: "SGP", flag: "🇸🇬", name: "Singapore Grand Prix",         circuit: "Marina Bay Street",             city: "Singapore",         date: "2026-10-04", laps: 62, length: 4.940 },
  { round: 18, country: "USA",         countryCode: "USA", flag: "🇺🇸", name: "United States Grand Prix",     circuit: "Circuit of the Americas",       city: "Austin",            date: "2026-10-25", laps: 56, length: 5.513 },
  { round: 19, country: "Mexico",      countryCode: "MEX", flag: "🇲🇽", name: "Mexico City Grand Prix",       circuit: "Hermanos Rodríguez",            city: "Mexico City",       date: "2026-11-01", laps: 71, length: 4.304 },
  { round: 20, country: "Brazil",      countryCode: "BRA", flag: "🇧🇷", name: "São Paulo Grand Prix",         circuit: "Interlagos",                    city: "São Paulo",         date: "2026-11-08", laps: 71, length: 4.309 },
  { round: 21, country: "USA",         countryCode: "USA", flag: "🇺🇸", name: "Las Vegas Grand Prix",         circuit: "Las Vegas Strip Circuit",       city: "Las Vegas",         date: "2026-11-21", laps: 50, length: 6.201 },
  { round: 22, country: "Qatar",       countryCode: "QAT", flag: "🇶🇦", name: "Qatar Grand Prix",             circuit: "Lusail International",          city: "Lusail",            date: "2026-11-29", laps: 57, length: 5.419 },
  { round: 23, country: "UAE",         countryCode: "UAE", flag: "🇦🇪", name: "Abu Dhabi Grand Prix",         circuit: "Yas Marina Circuit",            city: "Abu Dhabi",         date: "2026-12-06", laps: 58, length: 5.281 },
];

export function annotateCalendar(today: Date): CalendarRace[] {
  const t = today.getTime();
  let nextRoundSet = false;
  return CALENDAR_2026.map((r) => {
    const raceTime = new Date(r.date).getTime();
    if (raceTime < t) return { ...r, status: "past" as const };
    if (!nextRoundSet) {
      nextRoundSet = true;
      return { ...r, status: "next" as const };
    }
    return { ...r, status: "upcoming" as const };
  });
}
