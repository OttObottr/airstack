/* What counts as news: a vendor post that says something shipped, not a guide written for search engines. */
const SHIPS = /\b(introduc|announc|launch|now available|generally available|general availability|beta|preview|releas|rolls? out|rolling out|unveil|now supports?|support for|what'?s new|new in|is here|now in)\w*/i,
  FILLER = /\b(guide|how to|what is|what are|why |tips|ideas|best |top \d+|\d+ (ways|best|tips|steps)|vs\.?|webinar|podcast|survey|case study|explained|checklist|template)\b|\?$/i;
export const announced = i => i.kind === 'changelog' || (i.kind === 'blog' && SHIPS.test(i.title) && !FILLER.test(i.title));
