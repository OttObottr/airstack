/* Presentation choices, in one place: how far a view looks and how much it lists.
   Data windows are not here: each published file carries the params it was built with (lib/data.js PARAMS). */
export const VIEW = {
  homeAheadWeeks: 8 /* Home's "coming up" horizon */,
  homeShown: 6,
  calendarAgendaDays: 90,
  compareRecheckDays: 14 /* a comparison older than this is due a re-check */,
  compareShown: 8,
  moversTop: 12,
  tapeEnds: 15 /* a long momentum tape shows this many from each end */,
  attentionShown: 25,
};
