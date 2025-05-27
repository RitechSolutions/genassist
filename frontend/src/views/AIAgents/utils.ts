export function pairsToObject(pairs: Array<{key: string, value: unknown}>): Record<string, unknown> {
    return pairs.reduce((obj, pair) => {
      if (typeof pair.value === 'string') {
        try {
          const parsedValue = JSON.parse(pair.value);
          obj[pair.key] = parsedValue;
        } catch (e) {
          obj[pair.key] = pair.value;
        }
      } else {
        obj[pair.key] = pair.value;
      }
      console.log(`Key: ${pair.key}, Value: ${obj[pair.key]}`);
      return obj;
    }, {} as Record<string, unknown>);
  }
  
  export function objectToPairs(obj: Record<string, unknown>): Array<{key: string, value: unknown}> {
    return Object.entries(obj).map(([key, value]) => ({
      key,
      value
    }));
  } 