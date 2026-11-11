/* What leads the page: an item the pipeline's model read and judged to be news. A release counts when the model found something a user
   would act on; a thread counts when the page it discusses said something. No wording is matched here. */
export const announced = i => !!i.gist && i.signal !== 'other' && (i.kind !== 'release' || i.weight > 1);
/* what an item says: the model's sentence about its page where there is one, else the vendor's own headline */
export const says = i => i.gist || i.title;
