import { IDX, q, showTA } from './index.js';
import { esc, fd, ic, slug, sq } from '../../lib/format.js';
import { MK } from '../../lib/market.js';

export let DIR = null,
  KIDS = [];
let DIRP = null;
/* a listing's name where it is unique, else its id */
export const SLUGS = new Map();
export const addr = x => ((x.dir || x.org) && SLUGS.get(slug(x.name)) === x.id ? slug(x.name) : x.id);
export const loadDir = () =>
  DIRP ||
  (DIRP = fetch('directory.json')
    .then(r => {
      if (!r.ok) throw new Error(r.status);
      return r.json();
    })
    .then(D => {
      const T = D.types;
      const seen = new Map();
      for (const [id, name] of [
        ...D.products,
        ...Object.entries(D.orgs)
          .filter(([, o]) => o[5] !== 'person')
          .map(([id, o]) => [id, o[0]]),
      ]) {
        const s = slug(name);
        seen.set(s, seen.has(s) ? null : id);
      }
      seen.forEach((id, s) => id && SLUGS.set(s, id));
      KIDS = T.map(() => []);
      T.forEach((t, j) => t[2].forEach(p => KIDS[p].push(j)));
      KIDS.forEach(k => k.sort((a, b) => T[b][4] - T[a][4]));
      for (const [id, name, desc, site, t, devs, links, al] of D.products)
        IDX.push({
          id,
          name,
          lane: 'dir',
          laneName: T[t][1],
          k: sq(name),
          ak: (al || []).map(sq),
          dir: true,
          listed: true,
          desc,
          site,
          t,
          devs,
          links,
        });
      for (const [id, [name, site, country, founded, made, kind]] of Object.entries(D.orgs))
        if (kind !== 'person')
          IDX.push({
            id,
            name,
            lane: 'org',
            laneName: 'Organization',
            k: sq(name),
            ak: [
              sq(
                name.replace(
                  /,?\s+(platforms|inc\.?|incorporated|corporation|corp\.?|llc|ltd\.?|limited|gmbh|co\.?|company|group|holdings)$/i,
                  ''
                )
              ),
            ].filter(a => a && a !== sq(name)),
            org: true,
            listed: true,
            site,
            country,
            founded,
            made,
            links: made,
          }); /* a person who made something is named on its card, not listed as a company */
      DIR = D;
      if (document.activeElement === q && q.value.trim()) showTA();
    })
    .catch(e => {
      DIRP = null;
      throw e;
    }));
export const wdLink = id =>
  `<a class="ext" href="https://www.wikidata.org/wiki/${esc(id)}" target="_blank" rel="noopener noreferrer">Wikidata ${esc(id)}${ic('out')}</a> <span class="meta">read ${fd(DIR.source.fetched_at)} · CC0</span>`;
export const orgName = d => (DIR && DIR.orgs[d] ? DIR.orgs[d][0] : '');
export const researchedFacts = x => (MK && MK.profiles && MK.profiles[x.id] ? MK.profiles[x.id].facts : 0);
