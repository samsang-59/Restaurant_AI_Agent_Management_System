const TAKE_ORDER_REASONS = {
  dish_not_found: (s) => `"${s.dish_name}" is not on the menu`,
  insufficient_quantity: (s) => `Only ${s.available} × ${s.dish_name} left (asked ${s.quantity})`,
  invalid_quantity: (s) => `Invalid quantity: ${s.quantity}`,
};

/** Human-readable one-liner for an agent step event. */
export function describeStep(s, max) {
  const attempt = s.attempt ? ` (failure ${s.attempt}/${max})` : "";
  switch (s.node) {
    case "understand":
      if (s.intent === "order" && s.dish_name && s.quantity != null) return `Understood order: ${s.quantity} × ${s.dish_name}`;
      if (s.intent === "invalid") return "Query is not about dining here";
      return "Needs more details from the guest";
    case "take_order":
      return s.status === "success"
        ? `Order accepted · ${s.quantity} × ${s.dish_name} reserved (₹${s.price})`
        : `Order rejected · ${(TAKE_ORDER_REASONS[s.reason] || (() => s.reason))(s)}${attempt}`;
    case "cook":
      return s.status === "success" ? `Kitchen cooked ${s.quantity} × ${s.dish_name}` : `Kitchen issue: ${s.reason}${attempt}`;
    case "serve":
      return s.status === "success" ? `Served ${s.quantity} × ${s.dish_name} to your table` : `Serving issue: ${s.reason}${attempt}`;
    case "respond":
      return "AI host is replying to you";
    case "served":
      return "Order complete";
    case "end_session":
      if (s.reason === "invalid") return "Session ended · off-topic query";
      return `Session ended · ${s.reason.replace("limit_", "")} failed ${max} times`;
    default:
      return s.node;
  }
}
