export default function MenuGrid({ items, compact = false }) {
  const byCategory = items.reduce((acc, item) => {
    (acc[item.category] ||= []).push(item);
    return acc;
  }, {});

  return (
    <div className={`menu ${compact ? "menu-compact" : ""}`}>
      {Object.entries(byCategory).map(([category, dishes]) => (
        <div key={category} className="menu-cat">
          <h3>{category}</h3>
          <ul>
            {dishes.map((d) => (
              <li key={d.name} className={d.available === 0 ? "sold-out" : ""}>
                <span className={`veg-mark ${d.veg ? "veg" : "nonveg"}`} title={d.veg ? "Vegetarian" : "Non-vegetarian"} />
                <div className="dish">
                  <div className="dish-top">
                    <span className="dish-name">{d.name}</span>
                    <span className="dish-price">₹{d.price}</span>
                  </div>
                  {!compact && <p className="dish-desc">{d.description}</p>}
                  <span className={`stock ${d.available === 0 ? "stock-out" : d.available <= 3 ? "stock-low" : ""}`}>
                    {d.available === 0 ? "Sold out" : `${d.available} left`}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
